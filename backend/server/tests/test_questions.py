"""The question conversation: replies, pick, revise and accept, against the fake Greenhouse form.

Runs use real headless Chromium only when a run gets as far as filling (the last step here).
"""
# pylint: disable=redefined-outer-name,unused-argument
import urllib.request

import pytest

from agent.forms.form_field import FieldAnswer
from server.questions import interpret, match_option
from server.tests.job_helpers import (FAKE_ASHBY_URL, SPONSORSHIP, WHY_HERE, add_job, apply, job_detail,
                                      set_up_profile)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


@pytest.fixture
def asking(client, app):
    """The fake job, run once: it waits on the sponsorship question."""
    set_up_profile(client)
    job = add_job(client)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["question"]["field"] == SPONSORSHIP
    return job["id"]


def question_url(job_id, part=""):
    return f"/api/jobs/{job_id}/question{part}"


def reply(client, job_id, text):
    response = client.post(question_url(job_id, "/messages"), json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_full_conversation_to_ready(client, app, asking):
    question = reply(client, asking, "nope, I don't")
    assert question["proposedAnswer"] == {"value": "No", "confidence": 96}
    assert question["messages"][-1] == {"from": "you", "text": "nope, I don't"}

    cleared = client.delete(question_url(asking, "/answer"))
    assert cleared.status_code == 200 and cleared.json()["proposedAnswer"] is None

    unsure = reply(client, asking, "maybe")
    assert unsure["proposedAnswer"] is None
    assert unsure["messages"][-1] == {
        "from": "agent", "text": "This field only takes one of: Yes, No. Which one fits?"}
    assert unsure["pickOptions"] == ["Yes", "No"]

    bad = client.put(question_url(asking, "/answer"), json={"value": "Maybe"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_option"

    picked = client.put(question_url(asking, "/answer"), json={"value": "No"})
    assert picked.status_code == 200
    assert picked.json()["proposedAnswer"] == {"value": "No", "confidence": 100}
    # The cached job list sees the same question.
    assert job_detail(client, asking)["question"]["proposedAnswer"]["value"] == "No"

    accepted = client.post(question_url(asking, "/accept"), json={"scope": "all"})
    assert accepted.status_code == 200, accepted.text
    job = accepted.json()
    assert job["state"] == "queued" and job["question"] is None and "fields" not in job
    assert client.get("/api/agent/status").json()["queue"][0] == asking
    saved = [a for a in client.get("/api/answers").json() if a["question"] == SPONSORSHIP]
    assert len(saved) == 1
    assert saved[0]["answer"] == "No" and saved[0]["company"] is None
    assert saved[0]["savedRecently"] is True and saved[0]["category"] == "Eligibility"
    assert saved[0]["source"].startswith("You answered on Fake Company’s form · ")
    timeline = app.state.store.read("jobs")[0]["timeline"]
    assert timeline[-1]["kind"] == "accent"
    assert timeline[-1]["text"] == f"You answered “{SPONSORSHIP}”"

    # The re-run asks the next unanswered field.
    assert app.state.worker.run_next() == asking
    essay = job_detail(client, asking)["question"]
    assert essay["field"] == WHY_HERE and essay["id"] == f"q-{asking}-2"
    assert essay["type"] == "confirm" and essay["defaultScope"] == "company"

    text = "I like building tools people use."
    assert reply(client, asking, text)["proposedAnswer"] == {"value": text, "confidence": 95}
    assert client.post(question_url(asking, "/accept"),
                       json={"scope": "company"}).status_code == 200
    why = [a for a in client.get("/api/answers").json() if a["question"] == WHY_HERE]
    assert len(why) == 1 and why[0]["company"] == "Fake Company" and why[0]["answer"] == text

    assert app.state.worker.run_next() == asking
    detail = job_detail(client, asking)
    assert detail["state"] == "ready", detail
    fields = {f["label"]: f for f in detail["fields"]}
    assert fields[SPONSORSHIP]["value"] == "No" and fields[WHY_HERE]["value"] == text


def test_claude_guess_is_quoted_and_yes_uses_it(client, app, monkeypatch):
    def fake_ask(form_field, _facts):
        if form_field.key == "question_2004":
            return FieldAnswer("I like the team.", "claude", 60, "A guess.")
        return FieldAnswer("", "claude", 0, "Not in the profile.")
    monkeypatch.setattr("server.agent_bridge.ask_claude", fake_ask)
    app.state.config.claude_enabled = True  # as if agent/.env had a key
    set_up_profile(client)
    app.state.answer_bank.upsert_by_question(SPONSORSHIP, "No", origin="manual")
    job = add_job(client)
    apply(client, job["id"])
    app.state.worker.run_next()

    question = job_detail(client, job["id"])["question"]
    assert question["field"] == WHY_HERE
    assert question["messages"][0]["text"].startswith("My best guess is “I like the team.”")
    proposed = reply(client, job["id"], "yes")["proposedAnswer"]
    assert proposed == {"value": "I like the team.", "confidence": 97}


def test_no_question_and_no_answer(client, app, asking):
    other = add_job(client, FAKE_ASHBY_URL)
    for method, part, body in (("post", "/messages", {"text": "yes"}),
                               ("put", "/answer", {"value": "Yes"}),
                               ("delete", "/answer", None),
                               ("post", "/accept", {"scope": "all"})):
        kwargs = {"json": body} if body is not None else {}
        response = getattr(client, method)(question_url(other["id"], part), **kwargs)
        assert response.status_code == 404 and response.json()["code"] == "not_found"
    missing = client.post(question_url("job-nope", "/messages"), json={"text": "hi"})
    assert missing.status_code == 404
    response = client.post(question_url(asking, "/accept"), json={"scope": "all"})
    assert response.status_code == 409 and response.json()["code"] == "no_answer"
    assert job_detail(client, asking)["state"] == "needs_input"


def test_text_reply_drops_one_trailing_period_for_text_fields_only():
    question = {"messages": [{"from": "agent", "text": "What should I enter?"}],
                "proposedAnswer": None, "pickOptions": None}
    interpret(question, {"kind": "text", "options": []}, "Boston, MA.")
    assert question["proposedAnswer"] == {"value": "Boston, MA", "confidence": 95}
    interpret(question, {"kind": "textarea", "options": []}, "  I like it.  ")
    assert question["proposedAnswer"]["value"] == "I like it."


def test_date_reply_is_read_as_a_date_or_asked_again():
    """A date reply is kept as YYYY-MM-DD so the form can take it; anything else is asked again."""
    question = {"messages": [{"from": "agent", "text": "What should I enter?"}],
                "proposedAnswer": None, "pickOptions": None}
    interpret(question, {"kind": "date", "options": []}, "whenever")
    assert question["proposedAnswer"] is None
    assert question["messages"][-1]["text"] == ("This field takes a date, like June 1, 2027. "
                                                "What date should I put?")
    interpret(question, {"kind": "date", "options": []}, "June 1st, 2027.")
    assert question["proposedAnswer"] == {"value": "2027-06-01", "confidence": 95}


@pytest.mark.parametrize("text,expected", [
    ("she/her", "She"), ("They", "They"), ("i'd say she", "She"), ("th", "They"),
    ("he or she", None), ("", None)])
def test_match_option(text, expected):
    assert match_option(text, ["She", "He", "They"]) == expected


def test_option_reply_must_match_an_option():
    options = ["Boston", "New York", "Remote"]
    question = {"messages": [{"from": "agent", "text": "Pick one"}], "proposedAnswer": None,
                "pickOptions": None}
    interpret(question, {"kind": "select", "options": options}, "somewhere sunny")
    assert question["proposedAnswer"] is None and question["pickOptions"] == options
    assert question["messages"][-1]["text"] == ("This field only takes one of: Boston, New York, "
                                                "Remote. Which one fits?")
    interpret(question, {"kind": "select", "options": options}, "new york please")
    assert question["proposedAnswer"] == {"value": "New York", "confidence": 96}
