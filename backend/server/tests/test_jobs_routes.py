"""Jobs routes: add, duplicates, apply, the daily limit, cancel, skip/restore, restart recovery."""
import json
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from server import jobs
from server.tests.job_helpers import (ASHBY_URL, FAKE_URL, add_job, apply, job_detail,
                                      set_up_profile)

JOB_KEYS = {"id", "company", "role", "location", "ats", "url", "source", "postedAt", "addedAt",
            "closesOn", "reason", "checks", "skipSuggested", "state", "phase", "progress",
            "formSummary", "question", "readyAt"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Nothing in these tests may fetch a posting: the fake form is local files."""
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


def test_add_fake_greenhouse_job(signed_in, app):
    job = add_job(signed_in)
    assert set(job) == JOB_KEYS
    assert job["company"] == "Fake Company"
    assert job["role"] == "Software Engineering Intern"
    assert job["ats"] == "Greenhouse" and job["state"] == "open" and job["source"] == "added"
    assert job["url"] == FAKE_URL
    assert job["formSummary"]["totalFields"] == 11
    assert job["progress"] == {"filled": 0, "total": 11}
    assert job["id"].startswith("job-") and job["addedAt"]
    assert job["checks"][0] == {"status": "ok", "text": "Greenhouse form · 11 questions"}
    # No resume and no answers yet: resume, sponsorship and the essay aren't covered.
    assert job["formSummary"]["fieldsToAsk"] == 3
    assert job["checks"][1]["status"] == "warn"
    assert job["reason"] == "Asks 3 questions your profile doesn't cover"

    stored = app.state.store.read("jobs")[0]
    assert stored["internal"]["link"] == {"url": FAKE_URL, "site": "greenhouse",
                                          "company": "fakecompany", "job_id": "1001",
                                          "pasted": FAKE_URL}
    assert stored["internal"]["jobData"]["id"] == 1001
    assert stored["timeline"][0]["text"] == "You added the link"
    listed = signed_in.get("/api/jobs").json()
    assert [j["id"] for j in listed] == [job["id"]] and set(listed[0]) == JOB_KEYS
    detail = job_detail(signed_in, job["id"])
    assert detail["fields"] == [] and detail["currentField"] is None
    assert "internal" not in detail and "timeline" not in detail


def test_form_summary_counts_profile_and_bank(client, app):
    set_up_profile(client)  # resume uploaded
    app.state.answer_bank.upsert_by_question(
        "Will you now or in the future require visa sponsorship to work in the United States?",
        "No", origin="manual")
    job = add_job(client)
    assert job["formSummary"] == {"totalFields": 11, "fieldsToAsk": 1}
    assert job["reason"] == "Asks 1 question your profile doesn't cover"
    assert job["checks"][1]["text"] == ("1 required question isn't covered by your profile or "
                                        "Answer bank yet")


def test_duplicate_link_is_already_in_inbox(signed_in):
    job = add_job(signed_in)
    again = signed_in.post("/api/jobs", json={
        "url": "https://boards.greenhouse.io/fakecompany/jobs/1001"})
    assert again.status_code == 409
    body = again.json()
    assert body["code"] == "already_in_inbox"
    assert body["details"] == {"code": "already_in_inbox", "company": "Fake Company",
                               "role": "Software Engineering Intern", "jobId": job["id"]}


def test_already_applied(signed_in, app):
    with app.state.store.tx() as db:
        db.applications.append({"id": "app-x", "url": FAKE_URL, "company": "Fake Company",
                                "role": "Software Engineering Intern", "submittedBy": "agent",
                                "submittedAt": "2026-10-20T13:41:00Z"})
    response = signed_in.post("/api/jobs", json={"url": FAKE_URL})
    assert response.status_code == 409
    assert response.json()["details"] == {
        "code": "already_applied", "company": "Fake Company",
        "role": "Software Engineering Intern", "sentAt": "2026-10-20T13:41:00Z"}


@pytest.mark.parametrize("url,code", [
    ("https://www.linkedin.com/jobs/view/1", "unsupported_site"),
    ("https://jobs.lever.co/x/y", "unsupported_site"),
    ("https://boards.greenhouse.io/fakecompany", "invalid_url"),
    ("not a link", "invalid_url"),
    ("ftp://job-boards.greenhouse.io/fakecompany/jobs/1001", "invalid_url"),
    ("https://app.ashbyhq.com/x", "invalid_url"),
])
def test_rejected_links(signed_in, url, code):
    response = signed_in.post("/api/jobs", json={"url": url})
    assert response.status_code == 422
    assert response.json()["code"] == code
    assert signed_in.get("/api/jobs").json() == []


def test_unsupported_site_message_names_the_host(signed_in):
    body = signed_in.post("/api/jobs", json={"url": "https://www.linkedin.com/jobs/view/1"}).json()
    assert body["message"] == ("Auto Apply adds jobs from Greenhouse and Ashby links. "
                               "This one is from www.linkedin.com.")


def test_real_greenhouse_closed_posting(signed_in, monkeypatch):
    """A real (non-fake) Greenhouse posting that the Job Board API 404s is posting_closed."""
    def gone(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", gone)
    response = signed_in.post("/api/jobs", json={
        "url": "https://job-boards.greenhouse.io/othercompany/jobs/42"})
    assert response.status_code == 422 and response.json()["code"] == "posting_closed"

    def broken(url, timeout):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", broken)
    response = signed_in.post("/api/jobs", json={
        "url": "https://job-boards.greenhouse.io/othercompany/jobs/42"})
    assert response.status_code == 502 and response.json()["code"] == "fetch_failed"


def test_add_ashby_job(signed_in):
    job = add_job(signed_in, ASHBY_URL)
    assert job["ats"] == "Ashby" and job["company"] == "Acme" and job["role"] == "Ashby posting"
    assert job["formSummary"] is None and job["location"] == ""
    assert job["checks"] == [{"status": "warn", "text": "AutoApply can't fill Ashby forms yet. "
                                                        "You'll finish this one on the site."}]


def test_apply_needs_a_confirmed_profile(signed_in):
    job = add_job(signed_in)
    response = signed_in.post("/api/jobs/apply", json={"jobIds": [job["id"]]})
    assert response.status_code == 409 and response.json()["code"] == "profile_not_confirmed"
    assert job_detail(signed_in, job["id"])["state"] == "open"


def test_apply_queues_the_job(client):
    set_up_profile(client)
    job = add_job(client)
    assert apply(client, job["id"]) == {"queued": [job["id"]], "deferred": []}
    assert job_detail(client, job["id"])["state"] == "queued"
    assert client.get("/api/agent/status").json()["queue"] == [job["id"]]
    # Applying again (or applying unknown ids) changes nothing.
    assert apply(client, job["id"], "job-nope") == {"queued": [], "deferred": []}


def test_daily_limit_defers_the_rest(client):
    set_up_profile(client)
    first = add_job(client)
    second = add_job(client, ASHBY_URL)
    assert client.patch("/api/settings", json={"dailyLimit": 1}).status_code == 200
    assert apply(client, first["id"], second["id"]) == {"queued": [first["id"]],
                                                        "deferred": [second["id"]]}
    assert job_detail(client, second["id"])["state"] == "waiting"
    assert client.get("/api/agent/status").json()["queue"] == [first["id"], second["id"]]

    # Raising the limit releases the waiting job (PATCH /settings calls promote_waiting).
    assert client.patch("/api/settings", json={"dailyLimit": 2}).status_code == 200
    assert job_detail(client, second["id"])["state"] == "queued"
    assert client.get("/api/agent/status").json()["queue"] == [first["id"], second["id"]]


def test_sent_today_counts_against_the_limit(client, app):
    set_up_profile(client)
    job = add_job(client)
    store = app.state.store
    with store.tx() as db:
        db.applications.append({"id": "app-1", "submittedBy": "agent",
                                "submittedAt": store.now_iso(), "url": "https://x"})
        db.settings["dailyLimit"] = 1
    assert apply(client, job["id"]) == {"queued": [], "deferred": [job["id"]]}
    with store.tx() as db:
        assert not jobs.promote_waiting(db, store.now())


def test_cancel_queued_and_waiting(client):
    set_up_profile(client)
    first = add_job(client)
    second = add_job(client, ASHBY_URL)
    client.patch("/api/settings", json={"dailyLimit": 1})
    apply(client, first["id"], second["id"])
    response = client.post("/api/jobs/cancel", json={"jobIds": [first["id"], second["id"]]})
    assert response.status_code == 204 and response.content == b""
    for job in (first, second):
        detail = job_detail(client, job["id"])
        assert detail["state"] == "open" and detail["progress"]["filled"] == 0
    assert client.get("/api/agent/status").json()["queue"] == []


def test_cancel_running_job_detaches_the_run(client, app):
    set_up_profile(client)
    job = add_job(client)
    with app.state.store.tx() as db:
        record = jobs.find(db, job["id"])
        record.update(state="running", phase="filling", currentField="Email")
        record["internal"]["runId"] = "run-1"
        record["internal"]["claudeCache"] = {"question_2004": {"value": "x", "confidence": 50,
                                                               "reason": ""}}
    client.post("/api/jobs/cancel", json={"jobIds": [job["id"]]})
    detail = job_detail(client, job["id"])
    assert detail["state"] == "open" and detail["phase"] is None
    assert detail["currentField"] is None and detail["fields"] == []
    internal = app.state.store.read("jobs")[0]["internal"]
    assert internal["cancelRequested"] is True and internal["runId"] is None
    assert internal["claudeCache"] == {}


def test_skip_and_restore(client):
    set_up_profile(client)
    job = add_job(client)
    apply(client, job["id"])
    assert client.post(f"/api/jobs/{job['id']}/skip").status_code == 204
    assert client.get("/api/jobs").json() == []
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404
    assert client.get("/api/agent/status").json()["queue"] == []

    restored = client.post(f"/api/jobs/{job['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["state"] == "open" and restored.json()["id"] == job["id"]
    assert [j["id"] for j in client.get("/api/jobs").json()] == [job["id"]]
    # Restoring a job that isn't skipped is a 404.
    assert client.post(f"/api/jobs/{job['id']}/restore").status_code == 404


def test_adding_a_skipped_link_restores_it(signed_in):
    job = add_job(signed_in)
    signed_in.post(f"/api/jobs/{job['id']}/skip")
    again = signed_in.post("/api/jobs", json={"url": FAKE_URL})
    assert again.status_code == 201
    assert again.json()["id"] == job["id"] and again.json()["state"] == "open"


def test_unknown_job_ids_are_404(signed_in):
    for method, path in [("get", "/api/jobs/job-nope"), ("post", "/api/jobs/job-nope/skip"),
                         ("post", "/api/jobs/job-nope/restore")]:
        response = getattr(signed_in, method)(path)
        assert response.status_code == 404 and response.json()["code"] == "not_found"


def _running_job(job_id: str, phase: str) -> dict:
    return {"id": job_id, "company": "Fake Company", "role": "Intern", "location": "",
            "ats": "Greenhouse", "url": FAKE_URL, "source": "added", "postedAt": None,
            "addedAt": "2026-11-01T10:00:00Z", "closesOn": None, "reason": "Added from a link",
            "checks": [], "skipSuggested": False, "state": "running", "phase": phase,
            "progress": {"filled": 4, "total": 11}, "formSummary": None, "question": None,
            "readyAt": None, "fields": [{"label": "Email"}], "currentField": "Phone",
            "timeline": [], "approvedAt": "2026-11-01T10:00:00Z",
            "internal": {"link": {"url": FAKE_URL, "site": "greenhouse",
                                  "company": "fakecompany", "job_id": "1001"},
                         "runId": "run-old", "cancelRequested": False}}


def test_restart_recovery(data_dir, make_app):
    data_dir.mkdir(parents=True)
    other = {**_running_job("job-other", "filling"), "state": "queued", "phase": None}
    (data_dir / "jobs.json").write_text(json.dumps([
        other, _running_job("job-filling", "filling"), _running_job("job-sending", "submitting"),
    ]), encoding="utf-8")
    (data_dir / "state.json").write_text(json.dumps({"queue": ["job-other", "job-filling"]}),
                                         encoding="utf-8")
    app = make_app()
    with TestClient(app) as client:
        assert client.get("/api/agent/status").json()["queue"] == ["job-filling", "job-other"]
        filling = job_detail(client, "job-filling")
        assert filling["state"] == "queued" and filling["phase"] is None
        assert filling["fields"] == [] and filling["currentField"] is None
        assert filling["progress"] == {"filled": 0, "total": 11}
        sending = job_detail(client, "job-sending")
        assert sending["state"] == "handoff"
        assert sending["reason"] == "The server restarted while submitting; check the site"
    stored = {j["id"]: j for j in app.state.store.read("jobs")}
    assert stored["job-filling"]["internal"]["runId"] is None
    assert json.loads((data_dir / "jobs.json").read_text(encoding="utf-8"))[1]["state"] \
        == "queued"
