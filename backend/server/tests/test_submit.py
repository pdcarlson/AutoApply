"""POST /jobs/:id/submit in both SUBMIT_REAL_FORM modes, and /jobs/:id/mark-submitted.

`submit_real_form=True` only ever runs against the local fake Greenhouse form (FAKE_GREENHOUSE).
A fill that reaches `ready` keeps its browser open; Submit presses Submit on that page. The app
only closes a window after a confirmed submit's screenshot; conftest closes the rest.
"""
# pylint: disable=redefined-outer-name,unused-argument
import threading
import time
import urllib.request

import pytest

from playwright.sync_api import BrowserType

from agent.runner.apply_run import NOT_CONFIRMED, RunResult
from server import jobs
from server.applications import REFILLED, WATCHING
from fastapi.testclient import TestClient

from server.tests.job_helpers import (ASHBY_URL, FAKE_URL, SPONSORSHIP, add_job, apply,
                                      job_detail, seed_fake_form_answers, set_up_profile,
                                      use_fake_form_variant)

SECOND_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1002"  # also the fake form


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


def make_ready(client, app, url=FAKE_URL) -> str:
    job = add_job(client, url)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["state"] == "ready"
    return job["id"]


@pytest.fixture
def ready(client, app):
    set_up_profile(client)
    seed_fake_form_answers(app)
    return make_ready(client, app)


def submit(client, job_id):
    return client.post(f"/api/jobs/{job_id}/submit")


def launches(monkeypatch) -> list:
    """Records every Chromium launch from now on."""
    seen, original = [], BrowserType.launch

    def spy(self, *args, **kwargs):
        seen.append(kwargs)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(BrowserType, "launch", spy)
    return seen


def test_dry_run_submit(client, app, ready):
    session = app.state.worker.forms.get(ready)
    assert session is not None and session.alive  # held open for the review
    response = submit(client, ready)
    assert session.alive and app.state.worker.forms.get(ready) is session  # nothing was sent
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["id"] == f"app-{ready}" and summary["jobId"] == ready
    assert summary["confirmation"] is None and summary["submittedBy"] == "agent"
    assert summary["status"] == "submitted" and summary["isNew"] is True
    assert "timeline" not in summary and "screenshotUrl" not in summary

    detail = client.get(f"/api/applications/{summary['id']}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{ready}-filled.png"
    image = client.get(detail["screenshotUrl"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    last = detail["timeline"][-1]
    assert last["kind"] == "amber" and last["text"] == (
        "Not sent: SUBMIT_REAL_FORM is off, so the agent didn't press Submit (dry run)")
    assert all(e["kind"] != "current" for e in detail["timeline"])
    assert detail["fields"] and detail["fields"] == app.state.store.read("jobs")[0]["fields"]

    assert ready not in [j["id"] for j in client.get("/api/jobs").json()]
    assert client.get(f"/api/jobs/{ready}").status_code == 404
    listed = client.get("/api/applications").json()
    assert listed[0]["id"] == summary["id"] and listed[0]["isNew"] is True
    assert client.get("/api/agent/status").json()["sentToday"] == 1

    again = client.post("/api/jobs", json={"url": FAKE_URL})
    assert again.status_code == 409 and again.json()["code"] == "already_applied"
    assert again.json()["details"]["sentAt"] == summary["submittedAt"]
    # A second submit of the same job is refused.
    assert submit(client, ready).status_code == 409


def test_real_submit_against_the_fake_form(client, app, ready, monkeypatch):
    """Submit presses Submit on the page held open since the fill: no new browser, no refill."""
    app.state.config.submit_real_form = True
    session = app.state.worker.forms.get(ready)
    assert session is not None and session.alive
    launched = launches(monkeypatch)
    phases = []
    worker = app.state.worker
    original = worker._on_event  # pylint: disable=protected-access

    def spy(ctx, is_submit, kind, data):
        original(ctx, is_submit, kind, data)
        if kind == "phase":
            phases.append(app.state.store.read("jobs")[0]["phase"])
    worker._on_event = spy  # pylint: disable=protected-access

    response = submit(client, ready)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["confirmation"]["reference"].startswith("GH-1001-")
    assert summary["confirmation"]["confirmedAt"] == summary["submittedAt"]
    assert phases == ["submitting", "confirming"]
    # Closed only because it was confirmed and the screenshot saved.
    assert launched == [] and not session.alive and len(app.state.worker.forms) == 0
    shots = app.state.store.dir("screenshots")
    assert (shots / f"{ready}-filled.png").is_file() and (shots / f"{ready}-result.png").is_file()

    detail = client.get(f"/api/applications/{summary['id']}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{ready}-filled.png"
    assert [e["kind"] for e in detail["timeline"][-2:]] == ["accent", "current"]
    count = len(detail["fields"])
    assert detail["timeline"][-2]["text"] == (f"Submitted via Greenhouse, {count} fields. "
                                              "Confirmation page received.")
    assert client.get("/api/agent/status").json()["sentToday"] == 1
    stored = app.state.store.read("applications")[0]
    assert stored["_resultScreenshot"] == f"{ready}-result.png"
    assert "_resultScreenshot" not in detail
    assert all(e["text"] != REFILLED for e in detail["timeline"])


def test_submit_fills_again_when_the_window_was_closed(client, app, ready, monkeypatch):
    """The user closed the review window: Submit fills the form again, and the timeline says so."""
    app.state.config.submit_real_form = True
    session = app.state.worker.forms.get(ready)
    session.call(lambda held: held.page.close())
    launched = launches(monkeypatch)
    response = submit(client, ready)
    assert response.status_code == 200, response.text
    assert len(launched) == 1 and not session.alive
    detail = client.get(f"/api/applications/app-{ready}").json()
    texts = [e["text"] for e in detail["timeline"]]
    assert texts.index(REFILLED) == len(texts) - 3  # before "Submitted via ..." and "Waiting"
    assert detail["confirmation"] is not None


def test_submit_after_a_restart_fills_again(client, app, ready, make_app):
    """A restarted server has no held window: it fills the form again, then submits."""
    restarted = make_app()
    restarted.state.config.submit_real_form = True
    with TestClient(restarted) as other:
        assert other.post("/api/auth/google", json={"returnTo": "/"}).status_code == 200
        response = submit(other, ready)
        assert response.status_code == 200, response.text
        detail = other.get(f"/api/applications/app-{ready}").json()
    assert REFILLED in [e["text"] for e in detail["timeline"]]


def test_submit_waits_for_a_late_confirmation(client, app, monkeypatch):
    """Submit waits (polling) for a thank-you page that shows up a few seconds late."""
    use_fake_form_variant(monkeypatch, "confirm_ms=2500")
    set_up_profile(client)
    seed_fake_form_answers(app)
    job_id = make_ready(client, app)
    app.state.config.submit_real_form = True
    started = time.monotonic()
    response = submit(client, job_id)
    assert response.status_code == 200, response.text
    assert 2.4 < time.monotonic() - started < 30
    assert response.json()["confirmation"] is not None


def test_verification_code_not_entered_in_time(client, app, monkeypatch):
    """The site asks for an emailed code and nobody types it in time: handoff, the reason says
    so, and the window stays open (test_held_forms covers what happens next)."""
    use_fake_form_variant(monkeypatch, "code=1")
    set_up_profile(client)
    seed_fake_form_answers(app)
    job_id = make_ready(client, app)
    app.state.config.submit_real_form = True
    app.state.config.confirm_timeout_s = 2
    session = app.state.worker.forms.get(job_id)
    response = submit(client, job_id)
    assert response.status_code == 502 and response.json()["code"] == "submit_unconfirmed"
    message = response.json()["message"]
    assert message.startswith("Greenhouse asked for the verification code it emailed you. "
                              "Enter it in the open form window")
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["reason"] == message
    last = app.state.store.read("jobs")[0]["timeline"][-1]
    assert (last["kind"], last["text"]) == ("amber", message)
    assert session.alive and session.watching and app.state.worker.forms.get(job_id) is session
    assert app.state.store.path("screenshots", f"{job_id}-result.png").is_file()


def test_submit_on_a_job_that_isnt_ready(client, app):
    set_up_profile(client)
    job = add_job(client)
    response = submit(client, job["id"])
    assert response.status_code == 409 and response.json()["code"] == "not_ready"
    assert submit(client, "job-nope").status_code == 409


def test_mark_submitted_on_a_handoff_job(client, app, unfillable):  # pylint: disable=unused-argument
    set_up_profile(client)
    job = add_job(client, ASHBY_URL)
    early = client.post(f"/api/jobs/{job['id']}/mark-submitted")
    assert early.status_code == 409 and early.json()["code"] == "not_handoff"
    apply(client, job["id"])
    app.state.worker.run_next()
    assert job_detail(client, job["id"])["state"] == "handoff"

    response = client.post(f"/api/jobs/{job['id']}/mark-submitted")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["submittedBy"] == "you" and summary["confirmation"] is None
    detail = client.get(f"/api/applications/{summary['id']}").json()
    assert detail["screenshotUrl"] is None
    assert detail["timeline"][-2]["text"] == "You finished it on Acme’s site"
    assert detail["timeline"][-1]["kind"] == "current"
    # The user's own submissions don't count toward the agent's daily limit.
    assert client.get("/api/agent/status").json()["sentToday"] == 0
    assert job["id"] not in [j["id"] for j in client.get("/api/jobs").json()]


def test_answer_deleted_before_submit_sends_what_was_reviewed(client, app):
    """With the review window still open, Submit sends the page as reviewed."""
    set_up_profile(client)
    ids = seed_fake_form_answers(app)
    job_id = make_ready(client, app)
    app.state.config.submit_real_form = True
    assert client.delete(f"/api/answers/{ids[SPONSORSHIP]}").status_code == 204
    response = submit(client, job_id)
    assert response.status_code == 200, response.text


def test_answer_deleted_before_a_refill_asks_again(client, app):
    """Without the window, the refill finds the answer gone and asks for it again."""
    set_up_profile(client)
    ids = seed_fake_form_answers(app)
    job_id = make_ready(client, app)
    app.state.worker.held_form(job_id).close()  # like a restart
    app.state.config.submit_real_form = True
    assert client.delete(f"/api/answers/{ids[SPONSORSHIP]}").status_code == 204
    response = submit(client, job_id)
    assert response.status_code == 409 and response.json()["code"] == "answers_changed"
    detail = job_detail(client, job_id)
    assert detail["state"] == "needs_input" and detail["question"]["field"] == SPONSORSHIP
    assert client.get("/api/applications").json() == []
    assert REFILLED in [e["text"] for e in app.state.store.read("jobs")[0]["timeline"]]


@pytest.mark.parametrize("pressed,code,state", [
    (False, "submit_failed", "ready"), (True, "submit_unconfirmed", "handoff")])
def test_failed_submit(client, app, ready, monkeypatch, pressed, code, state):
    app.state.config.submit_real_form = True
    session = app.state.worker.held_form(ready)

    def fake_submit(self, on_event=None, **_kwargs):  # pylint: disable=unused-argument
        if pressed:
            on_event("phase", name="submitting")
            return RunResult("failed", NOT_CONFIRMED, pressed=True)
        return RunResult("failed", "Something went wrong on the page: boom")
    monkeypatch.setattr("agent.runner.apply_run.HeldForm.submit", fake_submit)
    response = submit(client, ready)
    assert response.status_code == 502 and response.json()["code"] == code
    detail = job_detail(client, ready)
    assert detail["state"] == state and detail["phase"] is None
    assert session.alive and session.watching == pressed  # the window stays either way
    if pressed:
        assert detail["reason"].startswith(WATCHING)
    assert detail["fields"]  # review-time fields kept
    assert app.state.store.read("jobs")[0]["internal"]["runId"] is None
    assert client.get("/api/applications").json() == []


def test_submit_waits_for_a_fill_in_progress(client, app, ready):
    """A submit's browser run never overlaps a worker fill: it starts after the fill ends."""
    app.state.config.submit_real_form = True
    worker = app.state.worker
    second = add_job(client, SECOND_URL)
    apply(client, second["id"])

    log, lock = [], threading.Lock()
    fill_started, release = threading.Event(), threading.Event()
    original_execute, original_event = worker.execute, worker._on_event  # pylint: disable=protected-access

    def execute(ctx, submit=False):
        with lock:
            log.append(("start", ctx.job_id))
        try:
            return original_execute(ctx, submit)
        finally:
            with lock:
                log.append(("end", ctx.job_id))

    def on_event(ctx, is_submit, kind, data):
        original_event(ctx, is_submit, kind, data)
        if is_submit and kind == "phase" and data["name"] == "submitting":
            with lock:
                log.append(("submit", ctx.job_id))
        if not is_submit and kind == "filled" and not fill_started.is_set():
            fill_started.set()
            assert release.wait(30)
    worker.execute = execute
    worker._on_event = on_event  # pylint: disable=protected-access

    filler = threading.Thread(target=worker.run_next)
    filler.start()
    assert fill_started.wait(30)
    responses = []
    submitter = threading.Thread(target=lambda: responses.append(submit(client, ready)))
    submitter.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:  # the submit claims the job, then waits for the lock
        if app.state.store.read("jobs")[0]["state"] == "running":
            break
        time.sleep(0.02)
    time.sleep(0.5)
    with lock:
        assert ("submit", ready) not in log
    record = next(j for j in app.state.store.read("jobs") if j["id"] == ready)
    assert record["state"] == "running" and record["phase"] == "submitting"
    release.set()
    filler.join(60)
    submitter.join(60)
    assert responses and responses[0].status_code == 200, responses[0].text
    assert log == [("start", second["id"]), ("end", second["id"]), ("submit", ready)]


def test_worker_holds_back_while_a_submit_runs(client, app, ready):
    """While a submit has the browser, run_next starts no fill; the queued job waits its turn."""
    app.state.config.submit_real_form = True
    worker = app.state.worker
    second = add_job(client, SECOND_URL)
    apply(client, second["id"])
    in_submit, release = threading.Event(), threading.Event()
    original_event = worker._on_event  # pylint: disable=protected-access

    def on_event(ctx, is_submit, kind, data):
        original_event(ctx, is_submit, kind, data)
        if is_submit and kind == "phase" and not in_submit.is_set():
            in_submit.set()
            assert release.wait(30)
    worker._on_event = on_event  # pylint: disable=protected-access

    responses = []
    submitter = threading.Thread(target=lambda: responses.append(submit(client, ready)))
    submitter.start()
    assert in_submit.wait(30)
    assert worker.run_next() is None
    with app.state.store.tx() as db:
        assert jobs.find(db, second["id"])["state"] == "queued"
    release.set()
    submitter.join(60)
    assert responses[0].status_code == 200, responses[0].text
    assert worker.run_next() == second["id"]
