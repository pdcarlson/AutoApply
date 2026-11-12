import pytest


def test_settings_defaults(client):
    assert client.get("/api/settings").json() == {"confidenceThreshold": 90, "dailyLimit": 25}


def test_patch_settings_merges(client):
    response = client.patch("/api/settings", json={"dailyLimit": 10})
    assert response.status_code == 200
    assert response.json() == {"confidenceThreshold": 90, "dailyLimit": 10}
    assert client.get("/api/settings").json()["dailyLimit"] == 10
    assert client.get("/api/agent/status").json()["dailyLimit"] == 10


@pytest.mark.parametrize("patch", [
    {"dailyLimit": 0},
    {"dailyLimit": 51},
    {"confidenceThreshold": -1},
    {"confidenceThreshold": 101},
    {"dailyLimit": "5"},
    {"dailyLimit": True},
    {"confidenceThreshold": 50.5},
    [1, 2],
])
def test_patch_settings_rejects_invalid_values(client, patch):
    response = client.patch("/api/settings", json=patch)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_settings"
    assert client.get("/api/settings").json() == {"confidenceThreshold": 90, "dailyLimit": 25}


def test_patch_settings_bounds_are_inclusive(client):
    low = client.patch("/api/settings", json={"dailyLimit": 1, "confidenceThreshold": 0})
    high = client.patch("/api/settings", json={"dailyLimit": 50, "confidenceThreshold": 100})
    assert low.status_code == 200 and high.status_code == 200


def test_agent_status_pause_resume(client):
    assert client.get("/api/agent/status").json() == {
        "paused": False, "sentToday": 0, "dailyLimit": 25, "queue": []}
    paused = client.post("/api/agent/pause")
    assert paused.status_code == 200 and paused.json()["paused"] is True
    assert client.get("/api/agent/status").json()["paused"] is True
    assert client.post("/api/agent/resume").json()["paused"] is False


def test_sent_today_counts_agent_submissions_from_today(client, app):
    store = app.state.store
    with store.tx() as db:
        db.applications = [
            {"id": "app-1", "submittedBy": "agent", "submittedAt": store.now_iso()},
            {"id": "app-2", "submittedBy": "you", "submittedAt": store.now_iso()},
            {"id": "app-3", "submittedBy": "agent", "submittedAt": "2020-01-01T12:00:00Z"},
        ]
    assert client.get("/api/agent/status").json()["sentToday"] == 1


def test_preferences_round_trip(client):
    assert client.get("/api/preferences").json() == {
        "roleTypes": [], "fullTime": True, "internship": False}
    prefs = {"roleTypes": ["Frontend"], "fullTime": False, "internship": True}
    assert client.put("/api/preferences", json=prefs).json() == prefs
    assert client.get("/api/preferences").json() == prefs
    bad = client.put("/api/preferences", json={"roleTypes": "x"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_request"


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"ok": True, "submitRealForm": False, "fakeGreenhouse": True, "claude": False}
