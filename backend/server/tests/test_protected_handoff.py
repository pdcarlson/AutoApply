"""Protected steps (US8): a form with a CAPTCHA, sign-in, password or SSN field is filled
everywhere else, handed to the person in its open window, and recorded once they finish it.
"""
# pylint: disable=redefined-outer-name,unused-argument
import time
import urllib.request

import pytest

from agent.forms.protected import PasswordCheck, SsnCheck
from server import applications
from server.tests.job_helpers import (add_job, apply, job_detail, seed_fake_form_answers,
                                      set_up_profile, use_fake_form_variant)


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


def make_protected(client, app, monkeypatch, kind: str) -> str:
    """A job whose fake form has one protected step: filled, then `handoff`."""
    use_fake_form_variant(monkeypatch, f"protect={kind}")
    job = add_job(client)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    return job["id"]


def test_ssn_field_hands_the_filled_form_to_the_person(client, app, profile, monkeypatch):
    job_id = make_protected(client, app, monkeypatch, "ssn")
    detail = job_detail(client, job_id)
    assert detail["state"] == "handoff" and detail["question"] is None
    assert detail["reason"] == SsnCheck.message + applications.PROTECTED_HIDDEN
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


def test_reason_points_at_the_window_when_it_is_shown(client, app, profile, monkeypatch):
    job_id = make_protected(client, app, monkeypatch, "password")
    app.state.config.show_browser = True  # only the wording changes; the window is the same
    session = app.state.worker.forms.get(job_id)
    assert applications.protected_reason(app.state.config, session.result) \
        == PasswordCheck.message + applications.PROTECTED_WINDOW


def test_finishing_it_in_the_window_records_the_application(client, app, profile, monkeypatch):
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
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-filled.png"
    assert app.state.store.path("screenshots", f"{job_id}-result.png").is_file()
    assert client.get("/api/agent/status").json()["sentToday"] == 1


def test_mark_submitted_finishes_a_protected_handoff(client, app, profile, monkeypatch):
    job_id = make_protected(client, app, monkeypatch, "ssn")
    response = client.post(f"/api/jobs/{job_id}/mark-submitted")
    assert response.status_code == 200, response.text
    assert response.json()["submittedBy"] == "you" and response.json()["confirmation"] is None
    detail = client.get(f"/api/applications/app-{job_id}").json()
    assert detail["screenshotUrl"] == f"/api/screenshots/{job_id}-result.png"


def test_applying_again_keeps_the_protected_window(client, app, profile, monkeypatch):
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
