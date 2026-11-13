import json

import pytest
from fastapi.testclient import TestClient

from server.store import Store


def test_data_dir_gets_gitignore(app, data_dir):  # pylint: disable=unused-argument
    assert (data_dir / ".gitignore").read_text(encoding="utf-8").strip().endswith("*")


def test_writes_are_atomic_and_survive_restart(client, make_app, data_dir):
    client.patch("/api/settings", json={"dailyLimit": 7})
    client.post("/api/agent/pause")
    client.put("/api/preferences",
               json={"roleTypes": ["Backend “quoted”"], "fullTime": True, "internship": False})
    assert not list(data_dir.rglob("*.tmp"))
    assert json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))["dailyLimit"] == 7
    assert "“quoted”" in (data_dir / "preferences.json").read_text(encoding="utf-8")

    with TestClient(make_app()) as again:
        assert again.get("/api/settings").json()["dailyLimit"] == 7
        assert again.get("/api/agent/status").json()["paused"] is True
        assert again.get("/api/preferences").json()["roleTypes"] == ["Backend “quoted”"]


def test_read_only_tx_writes_nothing(tmp_path):
    store = Store(tmp_path)
    with store.tx() as db:
        assert db.settings["dailyLimit"] == 25
    assert not (tmp_path / "settings.json").exists()


def test_failed_tx_rolls_back_and_writes_nothing(tmp_path):
    store = Store(tmp_path)
    with store.tx() as db:
        db.settings["dailyLimit"] = 5
    with pytest.raises(RuntimeError):
        with store.tx() as db:
            db.settings["dailyLimit"] = 9
            raise RuntimeError("boom")
    assert store.read("settings")["dailyLimit"] == 5
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["dailyLimit"] == 5


def test_unserializable_change_is_rejected_without_tmp(tmp_path):
    store = Store(tmp_path)
    with store.tx() as db:
        db.settings["dailyLimit"] = 5
    with pytest.raises(TypeError):
        with store.tx() as db:
            db.settings["dailyLimit"] = object()
    assert store.read("settings")["dailyLimit"] == 5
    assert not list(tmp_path.glob("*.tmp"))


def test_nested_tx_saves_once_at_outer_exit(tmp_path):
    store = Store(tmp_path)
    with store.tx() as outer:
        with store.tx() as inner:
            assert inner is outer
            inner.state["paused"] = True
        assert not (tmp_path / "state.json").exists()
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["paused"] is True


def test_missing_keys_get_defaults_and_corrupt_files_are_moved_aside(tmp_path):
    (tmp_path / "state.json").write_text('{"signedIn": true}', encoding="utf-8")
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    store = Store(tmp_path)
    state = store.read("state")
    assert state["signedIn"] is True and state["queue"] == [] and state["profileConfirmed"] is False
    assert store.read("settings") == {"confidenceThreshold": 90, "dailyLimit": 25}
    assert list(tmp_path.glob("settings.corrupt-*.json"))


def test_older_applications_show_their_thank_you_page_screenshot(tmp_path):
    """Saved before the after-Submit screenshot became the shown one: it replaces the filled one."""
    (tmp_path / "applications.json").write_text(json.dumps([
        {"id": "app-a", "screenshotUrl": "/api/screenshots/a-filled.png",
         "_resultScreenshot": "a-result.png"},
        {"id": "app-b", "screenshotUrl": "/api/screenshots/b-filled.png"},
    ]), encoding="utf-8")
    assert Store(tmp_path).read("applications") == [
        {"id": "app-a", "screenshotUrl": "/api/screenshots/a-result.png"},
        {"id": "app-b", "screenshotUrl": "/api/screenshots/b-filled.png"},
    ]


def test_delete_account_empties_dir_but_keeps_gitignore(signed_in, app, data_dir):
    signed_in.patch("/api/settings", json={"dailyLimit": 3})
    (app.state.store.dir("screenshots") / "x-filled.png").write_bytes(b"png")
    (app.state.store.dir("resume") / "cv.pdf").write_bytes(b"%PDF")
    (data_dir / "answer_bank.json").write_text('{"userdata": {}}', encoding="utf-8")

    assert signed_in.delete("/api/account").status_code == 204
    assert sorted(p.name for p in data_dir.iterdir()) == [".gitignore"]
    assert signed_in.get("/api/session").status_code == 401
    assert signed_in.get("/api/settings").json()["dailyLimit"] == 25


def test_export_is_an_attachment(signed_in, app):
    with app.state.store.tx() as db:
        db.profile["_resumePath"] = "resume/cv.pdf"
        db.applications = [{"id": "app-j1", "submittedBy": "agent",
                            "submittedAt": "2026-10-20T13:41:00Z",
                            "screenshotUrl": "/api/screenshots/j1-filled.png"}]
        db.jobs = [{"id": "j1", "state": "open", "internal": {"jobData": {}}}]
    response = signed_in.get("/api/account/export")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert 'filename="auto-apply-export.json"' in disposition
    body = response.json()
    assert set(body) == {"exportedAt", "profile", "commonAnswers", "preferences", "settings",
                         "answers", "applications", "jobs"}
    assert "_resumePath" not in body["profile"]
    assert "screenshotUrl" not in body["applications"][0]
    assert "internal" not in body["jobs"][0]
