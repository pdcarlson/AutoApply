"""GET /applications, GET /applications/:id and PATCH /applications/:id (spec 2.11)."""
# pylint: disable=redefined-outer-name,unused-argument
from datetime import timedelta

import pytest

from server.store import iso


def _record(app_id, submitted_at, **extra):
    return {"id": app_id, "jobId": app_id[4:], "company": "Acme", "role": "Intern",
            "location": "Remote", "ats": "Greenhouse", "url": f"https://x/{app_id}",
            "status": "submitted", "submittedAt": submitted_at, "submittedBy": "agent",
            "confirmation": None, "fields": [{"label": "Email", "value": "a@b.c",
                                              "source": "Profile", "sourceKind": "profile",
                                              "confidence": 100}],
            "timeline": [{"kind": "muted", "text": "You added the link", "at": submitted_at},
                         {"kind": "current", "text": "Waiting for a reply",
                          "at": submitted_at}],
            "screenshotUrl": None, "_resultScreenshot": "x-result.png", **extra}


@pytest.fixture
def seeded(signed_in, app):
    store = app.state.store
    now = store.now()
    with store.tx() as db:
        db.applications = [_record("app-old", iso(now - timedelta(days=3))),
                           _record("app-new", iso(now - timedelta(hours=1)))]
    return signed_in


def test_list_is_newest_first_without_detail_keys(seeded):
    listed = seeded.get("/api/applications").json()
    assert [a["id"] for a in listed] == ["app-new", "app-old"]
    assert [a["isNew"] for a in listed] == [True, False]
    assert set(listed[0]) == {"id", "jobId", "company", "role", "location", "ats", "url",
                              "status", "submittedAt", "submittedBy", "confirmation", "isNew"}


def test_detail_and_not_found(seeded):
    detail = seeded.get("/api/applications/app-old").json()
    assert detail["fields"][0]["label"] == "Email" and detail["screenshotUrl"] is None
    assert len(detail["timeline"]) == 2 and "_resultScreenshot" not in detail
    missing = seeded.get("/api/applications/app-nope")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_patch_status(seeded):
    response = seeded.patch("/api/applications/app-new", json={"status": "interviewing"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "interviewing" and "timeline" not in response.json()
    timeline = seeded.get("/api/applications/app-new").json()["timeline"]
    assert timeline[-1]["text"] == "You marked it Interviewing"
    assert timeline[-1]["kind"] == "accent"
    assert all(e["kind"] != "current" for e in timeline)

    seeded.patch("/api/applications/app-new", json={"status": "rejected"})
    assert seeded.get("/api/applications/app-new").json()["timeline"][-1] == {
        "kind": "red", "text": "You marked it Rejected",
        "at": seeded.get("/api/applications/app-new").json()["timeline"][-1]["at"]}

    seeded.patch("/api/applications/app-new", json={"status": "submitted"})
    timeline = seeded.get("/api/applications/app-new").json()["timeline"]
    assert [e["kind"] for e in timeline[-2:]] == ["accent", "current"]
    assert timeline[-1]["text"] == "Waiting for a reply"


@pytest.mark.parametrize("body", [{"status": "bogus"}, {}, None])
def test_patch_rejects_unknown_status(seeded, body):
    response = seeded.patch("/api/applications/app-new", json=body)
    assert response.status_code == 422 and response.json()["code"] == "invalid_status"
    assert seeded.get("/api/applications/app-new").json()["status"] == "submitted"


def test_patch_unknown_application(seeded):
    response = seeded.patch("/api/applications/app-nope", json={"status": "offer"})
    assert response.status_code == 404
