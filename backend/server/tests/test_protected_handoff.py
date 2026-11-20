"""Forms with a step only the person may do: filled elsewhere, then handed over in the window."""
import time

import pytest

from agent.forms.protected import CAPTCHA, CaptchaCheck, Handoff, PasswordCheck, SsnCheck
from agent.runner.apply_run import RunResult
from server.applications import reasons
from server.tests.job_helpers import (add_job, apply, job_detail, refuse_network,
                                      seed_fake_form_answers, set_up_profile,
                                      use_fake_form_variant)


@pytest.fixture(name="offline", autouse=True)
def fixture_offline(monkeypatch):
    """Fail any test that tries to reach the network."""
    refuse_network(monkeypatch)


@pytest.fixture(name="profile")
def fixture_profile(client, app):
    """A profile and saved answers that fill the whole fake form."""
    set_up_profile(client)
    seed_fake_form_answers(app)


def make_protected(client, app, monkeypatch, kind: str) -> str:
    """A job whose fake form has one protected step: filled, then `handoff`."""
    use_fake_form_variant(monkeypatch, f"protect={kind}")
    job = add_job(client)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    return job["id"]


@pytest.mark.usefixtures("profile")
def test_ssn_field_hands_the_filled_form_to_the_person(client, app, monkeypatch):
    """The SSN box is left empty, the rest is filled, and the job waits in `handoff`."""
    job_id = make_protected(client, app, monkeypatch, "ssn")
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["question"] is None
    assert detail["reason"] == SsnCheck.message + reasons.PROTECTED_HIDDEN
    labels = [f["label"] for f in detail["fields"]]
    assert "First Name" in labels and "Social Security Number" not in labels
    assert detail["progress"] == {"filled": len(labels), "total": len(labels) + 1}
    assert client.get("/api/agent/status").json()["queue"] == []

    session = app.state.worker.forms.get(job_id)
    assert session.alive and session.watching and not session.pressed
    assert session.call(lambda held: held.page.locator("#question_2099").input_value()) == ""
    stored = app.state.store.read("jobs")[0]
    assert stored["internal"]["windowWatched"] is True
    assert all("Social Security" not in a["question"] for a in app.state.answer_bank.list())


@pytest.mark.usefixtures("profile")
def test_reason_points_at_the_window_when_it_is_shown(client, app, monkeypatch):
    """With the browser shown, the reason sends the person to the open window."""
    job_id = make_protected(client, app, monkeypatch, "password")
    app.state.config.show_browser = True  # only the wording changes; the window is the same
    session = app.state.worker.forms.get(job_id)
    assert reasons.protected_reason(app.state.config, session.result) \
        == PasswordCheck.message + reasons.PROTECTED_WINDOW


@pytest.mark.usefixtures("profile")
def test_finishing_it_in_the_window_records_the_application(client, app, monkeypatch):
    """The person does the step and presses Submit in the window; the agent records it."""
    job_id = make_protected(client, app, monkeypatch, "password")
    session = app.state.worker.forms.get(job_id)
    session.call(lambda held: held.page.get_by_role("button", name="Submit application").click())

    deadline = time.monotonic() + 20
    while session.alive and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not session.alive  # confirmed and screenshotted, so the window closed
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["confirmation"] is not None
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"  # the thank-you page
    assert app.state.store.path("screenshots", f"{job_id}-result.png").is_file()
    assert client.get("/api/agent/status").json()["sentToday"] == 1


@pytest.mark.usefixtures("profile")
def test_mark_submitted_finishes_a_protected_handoff(client, app, monkeypatch):
    """The person can also finish it elsewhere and mark it submitted."""
    job_id = make_protected(client, app, monkeypatch, "ssn")
    response = client.post(f"/api/jobs/{job_id}/mark-submitted")
    assert response.status_code == 200, response.text
    assert response.json()["submittedBy"] == "you" and response.json()["confirmation"] is None
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"


@pytest.mark.usefixtures("profile")
def test_applying_again_keeps_the_protected_window(client, app, monkeypatch):
    """Skipping and applying again reuses the open window and goes back to `handoff`."""
    job_id = make_protected(client, app, monkeypatch, "ssn")
    session = app.state.worker.forms.get(job_id)
    assert client.post(f"/api/jobs/{job_id}/skip").status_code == 204
    assert client.post(f"/api/jobs/{job_id}/restore").status_code == 200
    apply(client, job_id)
    assert app.state.worker.run_next() == job_id
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff"
    assert detail["reason"].startswith(SsnCheck.message)
    assert app.state.worker.forms.get(job_id) is session and session.alive


@pytest.mark.usefixtures("profile")
def test_a_refill_before_submit_that_finds_a_protected_step_hands_it_over(client, app, monkeypatch):
    """Submit without a window fills again first; a protected step there means no Submit."""
    job = add_job(client)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    app.state.worker.held_form(job["id"]).close()  # like a restart
    use_fake_form_variant(monkeypatch, "protect=ssn")
    app.state.config.submit_real_form = True
    response = client.post(f"/api/jobs/{job['id']}/submit")
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "protected_step"
    detail = job_detail(client, job["id"])
    assert detail["state"] == "handoff" and detail["asksForCode"] is False
    assert detail["reason"].startswith(SsnCheck.message)
    session = app.state.worker.forms.get(job["id"])
    assert session.alive and session.watching and not session.pressed


def test_a_captcha_after_submit_gets_its_own_wording(app):
    """A CAPTCHA the site shows after Submit is named in the watching reason."""
    result = RunResult("failed", pressed=True,
                       protected=[Handoff(CAPTCHA, "CAPTCHA", CaptchaCheck.message)])
    app.state.config.show_browser = True
    assert reasons.watching_reason({"ats": "Greenhouse"}, app.state.config, result) \
        == reasons.WATCHING_CAPTCHA.format(site="Greenhouse")
