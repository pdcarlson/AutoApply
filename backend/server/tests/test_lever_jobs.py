"""Lever jobs in the server: added, filled by the worker, asked about, reviewed and submitted,
all against the local fake Lever page (FAKE_GREENHOUSE routes it there too).
"""
# pylint: disable=redefined-outer-name,unused-argument
import urllib.request

import pytest

from server import applications
from server.tests.job_helpers import (FAKE_LEVER_URL, add_job, apply, job_detail,
                                      set_up_profile, use_fake_form_variant, wait_for_state)

SCHOOL = "Which school do you attend?"
WHY_HERE = "Why do you want to work here?"
AUTHORIZED = "Are you legally authorized to work in the United States?"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.lever_form.urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


@pytest.fixture
def lever_job(client, app):
    """A confirmed profile, and the fake Lever job applied (queued)."""
    set_up_profile(client)
    job = add_job(client, FAKE_LEVER_URL)
    apply(client, job["id"])
    return job["id"]


def seed_answers(app):
    bank = app.state.answer_bank
    for question, answer in ((SCHOOL, "Rensselaer Polytechnic Institute"),
                             (WHY_HERE, "I like building tools people use."),
                             (AUTHORIZED, "Yes")):
        bank.upsert_by_question(question, answer, origin="manual", source="Test")


def test_unanswered_lever_question_becomes_a_question(client, app, lever_job):
    """Work authorization comes from the setup answers; the school isn't known, so it's asked."""
    assert app.state.worker.run_next() == lever_job
    detail = job_detail(client, lever_job)
    assert detail["state"] == "needs_input"
    assert detail["question"]["field"] == SCHOOL
    assert detail["question"]["pickOptions"] == ["Hudson Valley Institute of Technology",
                                                 "Rensselaer Polytechnic Institute"]
    fields = {f["label"]: f["value"] for f in detail["fields"]}
    assert fields[AUTHORIZED] == "Yes"


def test_lever_job_fills_to_ready_and_submits(client, app, lever_job):
    seed_answers(app)
    assert app.state.worker.run_next() == lever_job
    detail = job_detail(client, lever_job)
    assert detail["state"] == "ready", detail.get("reason")
    fields = {f["label"]: f["value"] for f in detail["fields"]}
    assert fields["Full name"] == "Jordan Rivera"
    assert fields["Current location"] == "Poughkeepsie, NY"  # the example resume's city
    assert fields[SCHOOL] == "Rensselaer Polytechnic Institute"

    app.state.config.submit_real_form = True
    response = client.post(f"/api/jobs/{lever_job}/submit")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["confirmation"]["reference"].startswith("LV-")
    detail = client.get(f"/api/applications/app-{lever_job}").json()
    assert detail["ats"] == "Lever"
    assert detail["screenshotUrl"] == f"/api/screenshots/{lever_job}-filled.png"


def test_bot_check_rejection_after_the_person_submits_moves_to_handoff(client, app, lever_job,
                                                                       monkeypatch):
    """The person presses Submit in the held window and Lever turns it away: the job moves to
    `handoff` and says to finish it in their own browser. The window stays open."""
    use_fake_form_variant(monkeypatch, "verify=fail")
    seed_answers(app)
    assert app.state.worker.run_next() == lever_job
    session = app.state.worker.forms.get(lever_job)
    session.call(lambda held: held.page.locator("#btn-submit").click())

    detail = wait_for_state(client, lever_job, ("handoff",), timeout=15.0)
    assert detail["reason"] == applications.blocked_reason({"ats": "Lever"})
    assert session.alive and session.blocked
    assert client.get("/api/applications").json() == []
    assert client.post(f"/api/jobs/{lever_job}/mark-submitted").status_code == 200


def test_bot_check_rejection_after_the_app_submits(client, app, lever_job, monkeypatch):
    use_fake_form_variant(monkeypatch, "verify=fail")
    seed_answers(app)
    assert app.state.worker.run_next() == lever_job
    app.state.config.submit_real_form = True
    app.state.config.confirm_timeout_s = 1
    response = client.post(f"/api/jobs/{lever_job}/submit")
    assert response.status_code == 502 and response.json()["code"] == "submit_unconfirmed"
    reason = applications.blocked_reason({"ats": "Lever"})
    assert response.json()["message"] == reason
    detail = job_detail(client, lever_job)
    assert detail["state"] == "handoff" and detail["reason"] == reason
