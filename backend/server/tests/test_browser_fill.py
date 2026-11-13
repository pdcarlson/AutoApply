"""The extension's routes: the fill plan for a page link, the resume, and recording a job the
person submitted in their own browser. All against the local fake Lever page.
"""
# pylint: disable=redefined-outer-name,unused-argument
import urllib.request

import pytest

from server.tests.job_helpers import (ASHBY_URL, EXAMPLE_PDF, FAKE_LEVER_URL, add_job, apply,
                                      job_detail, set_up_profile, use_fake_form_variant)

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
    """A confirmed profile and the fake Lever job in the Inbox (not applied yet)."""
    set_up_profile(client)
    return add_job(client, FAKE_LEVER_URL)["id"]


def get_plan(client, url):
    return client.get("/api/extension/plan", params={"url": url})


def test_plan_before_the_agent_ran_uses_the_profile(client, app, lever_job):
    """With nothing filled yet, the plan still has what the profile and setup answers cover,
    and names the required questions nobody has answered."""
    response = get_plan(client, FAKE_LEVER_URL + "/apply")
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["jobId"] == lever_job and plan["ats"] == "Lever"
    assert plan["company"] == "Fake Lever Company"
    values = {f["label"]: f["value"] for f in plan["fields"]}
    assert values["Full name"] == "Jordan Rivera"
    assert values["Email"] == "jordan.rivera@example.com"
    assert values[AUTHORIZED] == "Yes"
    assert plan["unanswered"] == [SCHOOL, WHY_HERE]
    assert plan["protected"] == []
    assert plan["resume"] == {"key": "resume", "name": "example_resume.pdf",
                              "url": f"/api/extension/jobs/{lever_job}/resume"}
    by_key = {f["key"]: f for f in plan["fields"]}
    assert by_key["location"]["kind"] == "location"
    assert by_key["cards[abc][field0]"]["kind"] == "select"


def test_plan_after_a_fill_has_the_answers_the_agent_used(client, app, lever_job):
    bank = app.state.answer_bank
    bank.upsert_by_question(SCHOOL, "Rensselaer Polytechnic Institute", origin="manual",
                            source="Test")
    bank.upsert_by_question(WHY_HERE, "I like building tools people use.", origin="manual",
                            source="Test")
    apply(client, lever_job)
    assert app.state.worker.run_next() == lever_job
    assert job_detail(client, lever_job)["state"] == "ready"
    plan = get_plan(client, FAKE_LEVER_URL).json()
    values = {f["label"]: f["value"] for f in plan["fields"]}
    assert values[SCHOOL] == "Rensselaer Polytechnic Institute"
    assert values[WHY_HERE] == "I like building tools people use."
    assert plan["unanswered"] == []


def test_plan_errors(client, app, lever_job):
    assert get_plan(client, "https://www.linkedin.com/jobs/view/1").json()["code"] == "invalid_url"
    missing = get_plan(client, "https://jobs.lever.co/fakelever/another-job")
    assert missing.status_code == 404 and missing.json()["code"] == "not_in_inbox"
    add_job(client, ASHBY_URL)
    ashby = get_plan(client, ASHBY_URL)
    assert ashby.status_code == 409 and ashby.json()["code"] == "unsupported_site"


def test_resume_is_served_to_the_extension(client, app, lever_job):
    response = client.get(f"/api/extension/jobs/{lever_job}/resume")
    assert response.status_code == 200
    assert response.content == EXAMPLE_PDF.read_bytes()
    assert response.headers["content-type"] == "application/pdf"
    assert client.get("/api/extension/jobs/job-missing/resume").status_code == 404


def test_submitting_in_the_browser_records_the_application(client, app, lever_job):
    """From `open` (never run by the agent) straight to an application sent by the person."""
    response = client.post(f"/api/extension/jobs/{lever_job}/submitted")
    assert response.status_code == 200, response.text
    assert response.json()["submittedBy"] == "you"
    assert [a["jobId"] for a in client.get("/api/applications").json()] == [lever_job]
    again = client.post(f"/api/extension/jobs/{lever_job}/submitted")
    assert again.status_code == 200  # the thank-you page reported twice


def test_submitting_in_the_browser_after_the_bot_check_turned_the_agent_away(
        client, app, lever_job, monkeypatch):
    """The usual path: the agent filled it, Lever turned its window away, and the person then
    submitted it in their own browser with the extension."""
    use_fake_form_variant(monkeypatch, "verify=fail")
    bank = app.state.answer_bank
    bank.upsert_by_question(SCHOOL, "Rensselaer Polytechnic Institute", origin="manual",
                            source="Test")
    bank.upsert_by_question(WHY_HERE, "I like building tools.", origin="manual", source="Test")
    apply(client, lever_job)
    assert app.state.worker.run_next() == lever_job
    response = client.post(f"/api/extension/jobs/{lever_job}/submitted")
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/applications/app-{lever_job}").json()
    assert detail["submittedBy"] == "you" and detail["ats"] == "Lever"
    assert len(detail["fields"]) == 8


def test_bookmark_window_and_fill_script_are_served(client):
    """The "Fill with AutoApply" bookmark opens this window, which hands the page this script."""
    window = client.get("/api/extension/fill-window")
    assert window.status_code == 200 and window.headers["content-type"].startswith("text/html")
    assert "autoapply-fill" in window.text and "/api/extension/plan" in window.text
    script = client.get("/api/extension/fill.js")
    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    assert "fillLever" in script.text
