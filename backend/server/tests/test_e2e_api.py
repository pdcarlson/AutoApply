"""End to end through the API with the real worker thread, against the fake Greenhouse form.

Sign in, upload the example resume, set up the profile, add the fake link, apply, answer the
agent's two questions, wait for `ready`, check what was filled, then submit. Runs in both
SUBMIT_REAL_FORM modes. FAKE_GREENHOUSE (set by conftest) maps the link to
backend/agent/tests/fake_forms, so Chromium only opens a file:// page and nothing goes online.

Run just these with `python -m pytest server/tests -m e2e`.
"""
# pylint: disable=redefined-outer-name,unused-argument
import time
import urllib.request

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page

from server.agent_bridge import FAKE_FORMS
from server.tests.job_helpers import (FAKE_URL, SPONSORSHIP, WHY_HERE, add_job, apply,
                                      upload_resume, wait_for_state)

pytestmark = pytest.mark.e2e

FIELD_SOURCE_KINDS = {"resume", "profile", "common_questions", "answer_bank", "you", "draft",
                      "other"}
WHY_TEXT = "I like building tools that people use every day."
FAKE_FORM_URI = (FAKE_FORMS / "greenhouse_form.html").resolve().as_uri()
OPTIONAL_UNANSWERED = ("How did you hear about this job?", "Anything else we should know?")


@pytest.fixture
def network_calls(monkeypatch):
    """Every urlopen raises, and is recorded. The fake flow must never call it."""
    calls = []

    def refuse(url, *_args, **_kwargs):
        calls.append(getattr(url, "full_url", url))
        raise OSError(f"network is off in this test: {url}")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)
    return calls


@pytest.fixture
def opened_urls(monkeypatch):
    """Records every URL Chromium is sent to (Page.goto), from any thread."""
    urls = []
    original = Page.goto

    def spy(self, url, *args, **kwargs):
        urls.append(url)
        return original(self, url, *args, **kwargs)
    monkeypatch.setattr(Page, "goto", spy)
    return urls


@pytest.fixture
def live(make_app, network_calls):
    """An app whose AgentWorker thread is running, and a client for it."""
    app = make_app(start_worker=True)
    with TestClient(app) as client:
        assert app.state.worker.alive
        yield app, client
    assert not app.state.worker.alive


def wait_for_question(client, job_id, field, timeout=60.0) -> dict:
    """Waits until the job is parked on a question about `field`."""
    deadline = time.monotonic() + timeout
    while True:
        detail = wait_for_state(client, job_id, ("needs_input", "ready", "open", "handoff"),
                                timeout=max(0.1, deadline - time.monotonic()))
        assert detail["state"] == "needs_input", detail
        if detail["question"] and detail["question"]["field"] == field:
            return detail
        assert time.monotonic() < deadline, f"never asked about {field}: {detail['question']}"
        time.sleep(0.1)


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def set_up(client):
    """Steps 1-5: sign in, resume, profile country, common answers, confirm."""
    assert client.get("/api/session").status_code == 401
    ok(client.post("/api/auth/google", json={"returnTo": "/"}))
    assert ok(client.get("/api/session"))["profileConfirmed"] is False

    parse = upload_resume(client)
    assert parse["file"]["name"] == "example_resume.pdf"

    profile = ok(client.get("/api/profile"))
    assert (profile["firstName"], profile["lastName"]) == ("Jordan", "Rivera") and profile["email"]
    assert profile["resume"]["name"] == "example_resume.pdf"
    if not profile["country"]:
        update = {k: v for k, v in profile.items() if k not in ("resume", "unplaced")}
        update["country"] = "United States"
        assert ok(client.put("/api/profile", json=update))["country"] == "United States"

    common = ok(client.get("/api/common-answers"))
    common.update(workAuthorized="Yes", needsSponsorship="No")
    ok(client.put("/api/common-answers", json=common))
    assert ok(client.post("/api/profile/confirm"))["profileConfirmed"] is True


def answer_questions(client, job_id):
    """Steps 8-10: pick "No" for sponsorship (all companies), reply to the essay (this one)."""
    sponsorship = wait_for_question(client, job_id, SPONSORSHIP)["question"]
    assert sponsorship["pickOptions"] == ["Yes", "No"]
    picked = ok(client.put(f"/api/jobs/{job_id}/question/answer", json={"value": "No"}))
    assert picked["proposedAnswer"]["value"] == "No"
    queued = ok(client.post(f"/api/jobs/{job_id}/question/accept", json={"scope": "all"}))
    assert queued["question"] is None and queued["state"] in ("queued", "running")

    essay = wait_for_question(client, job_id, WHY_HERE)["question"]
    assert essay["defaultScope"] == "company"
    replied = ok(client.post(f"/api/jobs/{job_id}/question/messages", json={"text": WHY_TEXT}))
    assert replied["proposedAnswer"]["value"] == WHY_TEXT
    ok(client.post(f"/api/jobs/{job_id}/question/accept", json={"scope": "company"}))


def check_ready_fields(detail):
    """Step 11: what the review screen shows."""
    assert detail["state"] == "ready", detail
    fields = {f["label"]: f for f in detail["fields"]}
    for label in ("First Name", "Last Name", "Email", "Resume/CV", "Country"):
        assert fields.get(label, {}).get("value"), (label, sorted(fields))
    assert fields["First Name"]["value"] == "Jordan" and fields["Last Name"]["value"] == "Rivera"
    assert fields["Resume/CV"]["value"] == "example_resume.pdf"
    assert fields[SPONSORSHIP]["value"] == "No" and fields[SPONSORSHIP]["sourceKind"] == "you"
    assert fields[WHY_HERE]["value"] == WHY_TEXT
    for label in OPTIONAL_UNANSWERED:
        assert label not in fields
    for field in detail["fields"]:
        assert field["sourceKind"] in FIELD_SOURCE_KINDS, field
        assert 0 <= field["confidence"] <= 100 and field["source"], field
    assert detail["progress"]["filled"] == len(detail["fields"])


def run_flow(app, client, *, submit_real_form: bool) -> dict:
    """The whole flow. Returns the ApplicationDetail."""
    app.state.config.submit_real_form = submit_real_form
    set_up(client)

    job = add_job(client, FAKE_URL)
    assert job["company"] == "Fake Company" and job["state"] == "open"
    assert job["location"] == "New York, NY"  # from the fixture, like the real Job Board API
    result = apply(client, job["id"])
    assert result["queued"] == [job["id"]] and result["deferred"] == []

    answer_questions(client, job["id"])
    detail = wait_for_state(client, job["id"], ("ready", "open", "handoff", "needs_input"))
    check_ready_fields(detail)
    shot = app.state.store.path("screenshots", f"{job['id']}-filled.png")
    assert shot.is_file()

    summary = ok(client.post(f"/api/jobs/{job['id']}/submit"))  # blocks until done
    assert summary["jobId"] == job["id"] and summary["submittedBy"] == "agent"
    assert summary["company"] == "Fake Company" and summary["status"] == "submitted"
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404
    assert job["id"] not in [j["id"] for j in ok(client.get("/api/jobs"))]
    assert [a["id"] for a in ok(client.get("/api/applications"))] == [summary["id"]]
    assert ok(client.get("/api/agent/status"))["sentToday"] == 1

    app_detail = ok(client.get(f"/api/applications/{summary['id']}"))
    assert app_detail["fields"] == detail["fields"]
    image = client.get(app_detail["screenshotUrl"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG")

    answers = ok(client.get("/api/answers"))
    sponsorship = [a for a in answers if a["question"] == SPONSORSHIP]
    why = [a for a in answers if a["question"] == WHY_HERE]
    assert len(sponsorship) == 1 and sponsorship[0]["answer"] == "No"
    assert sponsorship[0]["company"] is None and sponsorship[0]["savedRecently"] is True
    assert len(why) == 1 and why[0]["answer"] == WHY_TEXT and why[0]["company"] == "Fake Company"
    return app_detail


def test_e2e_dry_run(live, opened_urls):
    """SUBMIT_REAL_FORM off: the review fill is the last browser run; nothing is pressed."""
    app, client = live
    detail = run_flow(app, client, submit_real_form=False)
    assert detail["confirmation"] is None
    assert detail["timeline"][-1]["kind"] == "amber"
    assert detail["timeline"][-1]["text"].startswith("Not sent: SUBMIT_REAL_FORM is off")
    assert opened_urls and all(url.startswith("file://") for url in opened_urls)


def test_e2e_real_submit_against_the_fake_form(live, opened_urls):
    """SUBMIT_REAL_FORM on: the agent presses Submit on the local fake form and sees the
    confirmation page."""
    app, client = live
    detail = run_flow(app, client, submit_real_form=True)
    assert detail["confirmation"]["reference"].startswith("GH-1001-")
    assert [e["kind"] for e in detail["timeline"][-2:]] == ["accent", "current"]
    assert "Confirmation page received" in detail["timeline"][-2]["text"]
    shots = app.state.store.dir("screenshots")
    assert (shots / f"{detail['jobId']}-result.png").is_file()
    assert opened_urls and all(url.startswith("file://") for url in opened_urls)


def test_e2e_never_reaches_the_network(live, network_calls, opened_urls):
    """urlopen raises for the whole flow (both the fill and a real submit) and nothing calls it.
    Chromium is only ever sent to the local fake form."""
    app, client = live
    run_flow(app, client, submit_real_form=True)
    assert network_calls == []
    assert opened_urls and set(opened_urls) == {FAKE_FORM_URI}
