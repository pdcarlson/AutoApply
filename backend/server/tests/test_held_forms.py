"""Filled forms held open: the software never closes one unless the application was submitted
and a screenshot of that was saved. These tests cover every user action that used to close a
window, the watch after an unconfirmed Submit, mark-submitted, and the person closing it.

Only the local fake Greenhouse form is used (FAKE_GREENHOUSE, set by conftest). Windows the app
leaves open are closed by the `make_app` fixture's test-only teardown.
"""
# pylint: disable=redefined-outer-name,unused-argument
import threading
import time
import urllib.request

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import BrowserType

from server import jobs
from server.jobs import RESTART_WINDOW_GONE
from server.applications import REFILLED, WATCHING_CODE, WINDOW_CLOSED
from server.tests.job_helpers import (FAKE_URL, add_job, apply, job_detail,
                                      seed_fake_form_answers, set_up_profile,
                                      use_fake_form_variant, wait_for_state)
from server.worker import REUSED, WINDOW_CLOSED_READY

SECOND_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1002"  # also the fake form


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


@pytest.fixture
def profile(client, app):
    set_up_profile(client)
    seed_fake_form_answers(app)


def make_ready(client, app, url=FAKE_URL) -> str:
    job = add_job(client, url)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["state"] == "ready"
    return job["id"]


def held(app, job_id):
    return app.state.worker.forms.get(job_id)


def launches(monkeypatch) -> list:
    seen, original = [], BrowserType.launch

    def spy(self, *args, **kwargs):
        seen.append(kwargs)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(BrowserType, "launch", spy)
    return seen


def wait_until(check, seconds=15.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    return False


def texts(app, job_id) -> list[str]:
    with app.state.store.tx() as db:
        return [e["text"] for e in jobs.find(db, job_id)["timeline"]]


def submit_unconfirmed(client, app, monkeypatch, variant="code=1", url=FAKE_URL) -> str:
    """A job whose Submit was pressed and that asks for an emailed code: `handoff`."""
    use_fake_form_variant(monkeypatch, variant)
    job_id = make_ready(client, app, url)
    app.state.config.submit_real_form = True
    app.state.config.confirm_timeout_s = 2
    response = client.post(f"/api/jobs/{job_id}/submit")
    assert response.status_code == 502 and response.json()["code"] == "submit_unconfirmed"
    return job_id


def test_ready_jobs_each_keep_their_window(client, app, profile):
    """The worker moves on to the next job while earlier ones stay open; there is no cap."""
    first = make_ready(client, app)
    second = make_ready(client, app, SECOND_URL)
    assert held(app, first).alive and held(app, second).alive
    assert app.state.worker.forms.job_ids() == [first, second]
    assert held(app, first).call(lambda form: form.usable())
    assert not hasattr(app.state.config, "held_forms_max")


def test_skip_keeps_the_window_and_applying_again_reuses_it(client, app, profile, monkeypatch):
    job_id = make_ready(client, app)
    session = held(app, job_id)
    assert client.post(f"/api/jobs/{job_id}/skip").status_code == 204
    assert session.alive and held(app, job_id) is session

    launched = launches(monkeypatch)
    assert client.post(f"/api/jobs/{job_id}/restore").status_code == 200
    apply(client, job_id)
    assert app.state.worker.run_next() == job_id
    detail = job_detail(client, job_id)
    assert detail["state"] == "ready" and detail["fields"]
    assert launched == [] and held(app, job_id) is session and session.alive
    assert texts(app, job_id)[-1] == REUSED


def test_cancel_keeps_the_window(client, app, profile):
    """Cancelling a job applied to again (window still open) leaves the window; it's reused."""
    job_id = make_ready(client, app)
    session = held(app, job_id)
    client.post(f"/api/jobs/{job_id}/skip")
    client.post(f"/api/jobs/{job_id}/restore")
    apply(client, job_id)
    assert client.post("/api/jobs/cancel", json={"jobIds": [job_id]}).status_code == 204
    assert job_detail(client, job_id)["state"] == "open" and session.alive
    apply(client, job_id)
    assert app.state.worker.run_next() == job_id
    assert job_detail(client, job_id)["state"] == "ready" and held(app, job_id) is session


def test_delete_account_keeps_every_window(client, app, profile):
    first = make_ready(client, app)
    second = make_ready(client, app, SECOND_URL)
    sessions = [held(app, first), held(app, second)]
    assert client.delete("/api/account").status_code == 204
    time.sleep(1.5)  # a watch tick or two
    assert all(s.alive for s in sessions)


def test_a_job_that_stops_being_ready_keeps_its_window(client, app, profile):
    """No safety-net sweep: the worker leaves windows alone whatever the job's state."""
    job_id = make_ready(client, app)
    session = held(app, job_id)
    with app.state.store.tx() as db:
        jobs.find(db, job_id)["state"] = "open"
    app.state.worker.run_next()
    assert session.alive and held(app, job_id) is session


def test_dry_run_submit_keeps_the_window(client, app, profile):
    job_id = make_ready(client, app)
    session = held(app, job_id)
    assert client.post(f"/api/jobs/{job_id}/submit").status_code == 200
    assert session.alive and session.call(lambda form: form.usable())


def test_the_person_closing_a_ready_window(client, app, profile):
    """Allowed: the session ends, the job stays `ready`, and Submit fills the form again."""
    job_id = make_ready(client, app)
    session = held(app, job_id)
    session.call(lambda form: form.page.close())
    assert wait_until(lambda: not session.alive)
    assert held(app, job_id) is None
    assert job_detail(client, job_id)["state"] == "ready"
    assert texts(app, job_id)[-1] == WINDOW_CLOSED_READY
    app.state.config.submit_real_form = True
    assert client.post(f"/api/jobs/{job_id}/submit").status_code == 200
    assert REFILLED in [e["text"] for e in
                        client.get(f"/api/applications/app-{job_id}").json()["timeline"]]


def test_unconfirmed_submit_keeps_watching_until_the_code_is_entered(client, app, profile,
                                                                    monkeypatch):
    """The request answers (handoff) but the window stays open and watched; once the person
    enters the code in the window, the application is recorded and only then is it closed."""
    job_id = submit_unconfirmed(client, app, monkeypatch)
    session = held(app, job_id)
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["asksForCode"] is True
    assert detail["reason"] == WATCHING_CODE.format(site="Greenhouse")
    time.sleep(2.5)  # well past the timeout: still open, still watched
    assert session.alive and session.watching
    assert client.get("/api/applications").json() == []

    session.call(lambda form: form.page.click("#verify"))  # the person types the code
    assert wait_until(lambda: not session.alive), "the confirmed window should close"
    assert client.get(f"/api/jobs/{job_id}").status_code == 404  # out of the Inbox
    app_detail = client.get(f"/api/applications/app-{job_id}").json()
    assert app_detail["submittedBy"] == "agent"
    assert app_detail["confirmation"]["reference"].startswith("GH-1001-")
    assert [e["kind"] for e in app_detail["timeline"][-2:]] == ["accent", "current"]
    assert app_detail["timeline"][-2]["text"].endswith("Confirmation page received.")
    assert client.get("/api/agent/status").json()["sentToday"] == 1
    shot = app.state.store.path("screenshots", f"{job_id}-result.png")
    assert shot.is_file()
    assert app_detail["screenshotUrl"] == f"/api/screenshots/{shot.name}"


def test_the_person_closing_a_watched_window(client, app, profile, monkeypatch):
    job_id = submit_unconfirmed(client, app, monkeypatch)
    session = held(app, job_id)
    session.call(lambda form: form.page.close())
    assert wait_until(lambda: not session.alive)
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["reason"] == WINDOW_CLOSED
    assert detail["asksForCode"] is False
    assert texts(app, job_id)[-1] == WINDOW_CLOSED
    assert client.get("/api/applications").json() == []


def enter_code(client, job_id, code):
    return client.post(f"/api/jobs/{job_id}/verification-code", json={"code": code})


@pytest.mark.parametrize("variant", ["code=1", "code=boxes"])
def test_the_code_entered_in_the_app_submits_it(client, app, profile, monkeypatch, variant):
    """The agent types the code into the watched window and sends it: the application is
    recorded as a confirmed submit and the window closes. code=boxes is Greenhouse's real
    layout (one box per character, then Submit application again)."""
    job_id = submit_unconfirmed(client, app, monkeypatch, variant)
    session = held(app, job_id)
    response = enter_code(client, job_id, " ab12 CD34 ")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["submittedBy"] == "agent" and summary["confirmation"] is not None
    assert not session.alive
    assert client.get(f"/api/jobs/{job_id}").status_code == 404  # out of the Inbox
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["timeline"][-2]["text"].endswith("Confirmation page received.")
    assert client.get("/api/agent/status").json()["sentToday"] == 1
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"


@pytest.mark.parametrize("variant", ["code=1", "code=boxes"])
def test_a_wrong_code_can_be_tried_again(client, app, profile, monkeypatch, variant):
    """The site doesn't take the code: 422, the job still asks for one, the window stays open
    and watched, and the right code then goes through."""
    job_id = submit_unconfirmed(client, app, monkeypatch, variant)
    session = held(app, job_id)
    started = time.monotonic()
    response = enter_code(client, job_id, "00000000")  # the fake form rejects all zeros
    assert time.monotonic() - started < 15, "a shown error ends the wait early"
    assert response.status_code == 422 and response.json()["code"] == "code_rejected"
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["asksForCode"] is True
    assert session.alive and session.watching
    assert texts(app, job_id)[-1] == "Greenhouse didn’t take the code you entered"

    response = enter_code(client, job_id, "ABCD1234")
    assert response.status_code == 200, response.text
    assert not session.alive and client.get(f"/api/jobs/{job_id}").status_code == 404


def test_entering_a_code_needs_one_and_a_window_asking_for_it(client, app, profile,
                                                             monkeypatch):
    ready = make_ready(client, app)
    response = enter_code(client, ready, "ABCD1234")
    assert response.status_code == 409 and response.json()["code"] == "not_handoff"

    job_id = submit_unconfirmed(client, app, monkeypatch, url=SECOND_URL)
    response = enter_code(client, job_id, "  ")
    assert response.status_code == 422 and response.json()["code"] == "invalid_code"
    session = held(app, job_id)
    session.call(lambda form: form.page.close())
    assert wait_until(lambda: not session.alive)
    response = enter_code(client, job_id, "ABCD1234")
    assert response.status_code == 409 and response.json()["code"] == "no_code_window"
    assert job_detail(client, job_id)["state"] == "handoff"


def test_a_watched_window_survives_skip_and_apply_again(client, app, profile, monkeypatch):
    """A job whose window was submitted can't be filled again: back to handoff, same window."""
    job_id = submit_unconfirmed(client, app, monkeypatch)
    session = held(app, job_id)
    client.post(f"/api/jobs/{job_id}/skip")
    client.post(f"/api/jobs/{job_id}/restore")
    apply(client, job_id)
    assert app.state.worker.run_next() == job_id
    assert job_detail(client, job_id)["state"] == "handoff"
    assert held(app, job_id) is session and session.alive and session.watching


def test_a_restart_says_the_watched_window_is_gone(client, app, profile, monkeypatch, make_app):
    """The window ends with the old process; after a restart the handoff reason says so."""
    job_id = submit_unconfirmed(client, app, monkeypatch)
    restarted = make_app()
    with TestClient(restarted) as other:
        other.post("/api/auth/google", json={"returnTo": "/"})
        detail = job_detail(other, job_id)
    assert detail["state"] == "handoff" and detail["reason"] == RESTART_WINDOW_GONE


def test_mark_submitted_screenshots_the_window_then_closes_it(client, app, profile,
                                                             monkeypatch):
    job_id = submit_unconfirmed(client, app, monkeypatch)
    session = held(app, job_id)
    shot = app.state.store.path("screenshots", f"{job_id}-result.png")
    shot.unlink()
    response = client.post(f"/api/jobs/{job_id}/mark-submitted")
    assert response.status_code == 200, response.text
    assert response.json()["submittedBy"] == "you" and response.json()["confirmation"] is None
    assert shot.is_file() and not session.alive
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"
    assert client.get("/api/agent/status").json()["sentToday"] == 0


def test_mark_submitted_on_a_confirmed_window_records_a_confirmed_submit(client, app, profile,
                                                                        monkeypatch):
    job_id = submit_unconfirmed(client, app, monkeypatch)
    session = held(app, job_id)
    # The code goes in and mark-submitted follows at once, before the next watch tick.
    session.call(lambda form: form.page.click("#verify"))
    response = client.post(f"/api/jobs/{job_id}/mark-submitted")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["submittedBy"] == "agent" and summary["confirmation"] is not None
    assert wait_until(lambda: not session.alive)
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"
    assert client.get("/api/agent/status").json()["sentToday"] == 1


def test_shutdown_leaves_the_windows_to_the_process(make_app):
    """The lifespan's worker.stop() closes nothing; the windows end with the process (here,
    the test teardown closes them)."""
    app = make_app(start_worker=True)
    with TestClient(app) as client:
        set_up_profile(client)
        seed_fake_form_answers(app)
        job = add_job(client)
        apply(client, job["id"])
        assert wait_for_state(client, job["id"], ("ready", "open", "handoff"))["state"] == "ready"
        session = held(app, job["id"])
        assert session.alive
    assert not app.state.worker.alive
    assert session.alive and f"form-{job['id']}" in {t.name for t in threading.enumerate()}
    app.state.worker.close_forms_for_tests()
    assert not session.alive
