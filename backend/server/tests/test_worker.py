"""The AgentWorker against the fake Greenhouse form, with real headless Chromium.

Most tests call `app.state.worker.run_next()` directly (start_worker=False). One test runs the
real background thread, which is where Playwright's sync API runs in the server.
"""
# pylint: disable=redefined-outer-name,unused-argument
import threading
import urllib.request

import pytest
from fastapi.testclient import TestClient

from agent.forms.form_field import FieldAnswer, FormField
from server import jobs
from server.questions import make_question
from server.tests.job_helpers import (ASHBY_URL, SPONSORSHIP, WHY_HERE, add_job, apply,
                                      job_detail, seed_fake_form_answers, set_up_profile,
                                      wait_for_state)

SOURCE_KINDS = {"resume", "profile", "common_questions", "answer_bank", "you", "draft", "other"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


@pytest.fixture
def applied(client):
    """A confirmed profile with a resume, and the fake job applied (queued)."""
    set_up_profile(client)
    job = add_job(client)
    apply(client, job["id"])
    return job["id"]


def fields_by_label(detail):
    return {f["label"]: f for f in detail["fields"]}


def test_unanswered_sponsorship_becomes_a_question(client, app, applied):
    assert app.state.worker.run_next() == applied
    detail = job_detail(client, applied)
    assert detail["state"] == "needs_input" and detail["phase"] is None
    question = detail["question"]
    assert question["id"] == f"q-{applied}-1"
    assert question["type"] == "yesno" and question["pickOptions"] == ["Yes", "No"]
    assert question["field"] == SPONSORSHIP
    assert question["proposedAnswer"] is None and question["defaultScope"] == "all"
    assert question["placeholder"] == "e.g. Yes" and question["confidence"] == 0
    assert question["messages"] == [{"from": "agent", "text": (
        "Nothing in your profile or Answer bank answers this. Pick one, or reply in your own "
        "words.")}]

    fields = fields_by_label(detail)
    assert fields["First Name"] == {"label": "First Name", "value": "Jordan", "source": "Profile",
                                    "sourceKind": "profile", "confidence": 100}
    assert fields["Resume/CV"]["value"] == "example_resume.pdf"
    assert SPONSORSHIP not in fields and WHY_HERE not in fields
    assert detail["progress"] == {"filled": len(detail["fields"]), "total": 11}
    assert client.get("/api/agent/status").json()["queue"] == []

    stored = app.state.store.read("jobs")[0]
    assert stored["internal"]["question"] == {"fieldKey": "question_2002", "label": SPONSORSHIP,
                                              "kind": "select", "options": ["Yes", "No"]}
    assert stored["timeline"][-1]["kind"] == "amber"
    assert stored["timeline"][-1]["text"] == f"Paused on a question: {SPONSORSHIP}"
    # Nothing left to run.
    assert app.state.worker.run_next() is None


def test_essay_question_after_sponsorship_is_answered(client, app, applied):
    app.state.answer_bank.upsert_by_question(SPONSORSHIP, "No", origin="reply", source="Test")
    app.state.worker.run_next()
    question = job_detail(client, applied)["question"]
    assert question["field"] == WHY_HERE and question["type"] == "confirm"
    assert question["pickOptions"] is None and question["defaultScope"] == "company"
    assert question["placeholder"] == "A sentence or two in your own words"
    assert question["messages"][0]["text"] == ("Nothing in your profile or Answer bank answers "
                                               "this. What should I enter?")
    fields = fields_by_label(job_detail(client, applied))
    assert fields[SPONSORSHIP]["sourceKind"] == "you"
    assert fields[SPONSORSHIP]["source"].startswith("You answered · ")


def test_claude_guess_is_quoted_and_cached(client, app, applied, monkeypatch):
    app.state.answer_bank.upsert_by_question(SPONSORSHIP, "No", origin="manual")
    calls = []

    def fake_ask(form_field, _facts):
        calls.append(form_field.key)
        if form_field.key == "question_2004":
            return FieldAnswer("I like the team.", "claude", 60, "A guess.")
        return FieldAnswer("", "claude", 0, "Not in the profile.")
    monkeypatch.setattr("server.agent_bridge.ask_claude", fake_ask)

    app.state.worker.run_next()
    question = job_detail(client, applied)["question"]
    assert question["confidence"] == 60
    assert question["messages"][0]["text"] == (
        "My best guess is “I like the team.”, but I’m only 60% sure. Reply “yes” to use it, or "
        "tell me the right answer.")
    cache = app.state.store.read("jobs")[0]["internal"]["claudeCache"]
    assert cache == {"question_2004": {"value": "I like the team.", "confidence": 60,
                                       "reason": "A guess."}}
    # A second run (after re-queueing at the front) reads the guess from the cache.
    with app.state.store.tx() as db:
        jobs.requeue_at_front(db, jobs.find(db, applied))
    asked = list(calls)
    app.state.worker.run_next()
    assert "question_2004" not in calls[len(asked):]
    assert job_detail(client, applied)["question"]["id"] == f"q-{applied}-2"


def test_fills_to_ready_with_bank_answers(client, app, applied):
    ids = seed_fake_form_answers(app)
    assert app.state.worker.run_next() == applied
    detail = job_detail(client, applied)
    assert detail["state"] == "ready", detail
    assert detail["readyAt"] and detail["phase"] is None and detail["currentField"] is None
    assert detail["question"] is None
    assert detail["progress"]["filled"] == detail["progress"]["total"] == len(detail["fields"])
    assert app.state.store.path("screenshots", f"{applied}-filled.png").is_file()

    fields = fields_by_label(detail)
    assert fields["Resume/CV"]["value"] == "example_resume.pdf"
    assert fields[SPONSORSHIP]["sourceKind"] == "answer_bank"
    assert fields[WHY_HERE]["sourceKind"] == "you"
    assert fields["Country"]["value"] == "United States"
    assert {f["sourceKind"] for f in detail["fields"]} <= SOURCE_KINDS
    assert "Anything else we should know?" not in fields

    bank = app.state.answer_bank
    for answer_id in ids.values():
        record = bank.get(answer_id)
        assert record["timesUsed"] == 1 and record["lastUsedAt"]
        assert record["usedOn"][0]["company"] == "Fake Company"
    stored = app.state.store.read("jobs")[0]
    assert stored["internal"]["screenshot"] == f"{applied}-filled.png"
    assert stored["timeline"][-1]["text"] == "Filled and held for your review"
    assert client.get("/api/agent/status").json()["queue"] == []


def test_ashby_job_goes_to_handoff(client, app):
    set_up_profile(client)
    job = add_job(client, ASHBY_URL)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    detail = job_detail(client, job["id"])
    assert detail["state"] == "handoff"
    assert detail["reason"] == "AutoApply can't fill Ashby forms yet"
    assert client.get("/api/agent/status").json()["queue"] == []


def test_missing_resume_sends_the_job_back_to_open(client, app):
    set_up_profile(client, resume=False)
    seed_fake_form_answers(app)
    job = add_job(client)
    apply(client, job["id"])
    app.state.worker.run_next()
    detail = job_detail(client, job["id"])
    assert detail["state"] == "open"
    reason = "This form needs a resume. Add one on your Profile page."
    assert detail["checks"][0] == {"status": "bad", "text": reason}
    assert detail["reason"] == f"Last try didn't finish: {reason}"
    assert detail["fields"] == [] and detail["progress"]["filled"] == 0
    assert app.state.store.read("jobs")[0]["timeline"][-1]["kind"] == "red"


def test_failed_run_goes_back_to_open(client, app, applied, monkeypatch):
    seed_fake_form_answers(app)

    def boom(self, form, answered, shot_name):  # pylint: disable=unused-argument
        from agent.runner.apply_run import RunResult  # pylint: disable=import-outside-toplevel
        return RunResult("failed", "Something went wrong on the page: boom")
    monkeypatch.setattr("agent.runner.apply_run.ApplyRun.fill_and_send", boom)
    app.state.worker.run_next()
    detail = job_detail(client, applied)
    assert detail["state"] == "open"
    assert detail["reason"] == "Last try didn't finish: Something went wrong on the page: boom"
    # Applying again works, and a second failure doesn't stack another bad check.
    apply(client, applied)
    app.state.worker.run_next()
    checks = job_detail(client, applied)["checks"]
    assert [c["status"] for c in checks].count("bad") == 1


def test_paused_worker_runs_nothing(client, app, applied):
    client.post("/api/agent/pause")
    assert app.state.worker.run_next() is None
    assert job_detail(client, applied)["state"] == "queued"
    client.post("/api/agent/resume")
    assert app.state.worker.run_next() == applied


def test_run_next_promotes_waiting_jobs(client, app):
    set_up_profile(client)
    job = add_job(client, ASHBY_URL)
    with app.state.store.tx() as db:
        record = jobs.find(db, job["id"])
        record.update(state="waiting", approvedAt=app.state.store.now_iso())
    assert app.state.worker.run_next() == job["id"]  # promoted, then run
    assert job_detail(client, job["id"])["state"] == "handoff"


def test_cancel_mid_run_stops_between_fields(client, app, applied, monkeypatch):
    """Cancelling while the browser is filling stops the run; the job stays open and empty."""
    seed_fake_form_answers(app)
    worker = app.state.worker
    original = worker._on_event  # pylint: disable=protected-access

    def cancel_after_first_fill(ctx, submit, kind, data):
        original(ctx, submit, kind, data)
        if kind == "filled":
            response = client.post("/api/jobs/cancel", json={"jobIds": [applied]})
            assert response.status_code == 204
    monkeypatch.setattr(worker, "_on_event", cancel_after_first_fill)
    worker.run_next()
    detail = job_detail(client, applied)
    assert detail["state"] == "open"
    assert detail["fields"] == [] and detail["progress"]["filled"] == 0
    assert not app.state.store.path("screenshots", f"{applied}-filled.png").exists()


def test_worker_thread_fills_in_the_background(make_app):
    """The real worker thread: sync Playwright launches Chromium off the main thread."""
    app = make_app(start_worker=True)
    seen_threads = []
    worker = app.state.worker
    original = worker.execute

    def spy(ctx, submit=False):
        seen_threads.append(threading.current_thread().name)
        return original(ctx, submit)
    worker.execute = spy
    with TestClient(app) as client:
        assert worker.alive
        set_up_profile(client)
        seed_fake_form_answers(app)
        job = add_job(client)
        apply(client, job["id"])
        detail = wait_for_state(client, job["id"], ("ready", "open", "needs_input", "handoff"))
        assert detail["state"] == "ready", detail
        assert app.state.store.path("screenshots", f"{job['id']}-filled.png").is_file()
    assert seen_threads == ["agent-worker"]
    assert not worker.alive  # the lifespan stopped it


def test_worker_stop_mid_run_puts_the_job_back_in_line(client, app, applied, monkeypatch):
    seed_fake_form_answers(app)
    worker = app.state.worker
    original = worker._on_event  # pylint: disable=protected-access

    def stop_after_first_fill(ctx, submit, kind, data):
        original(ctx, submit, kind, data)
        if kind == "filled":
            worker._stopping.set()  # pylint: disable=protected-access
    monkeypatch.setattr(worker, "_on_event", stop_after_first_fill)
    worker.run_next()
    detail = job_detail(client, applied)
    assert detail["state"] == "queued" and detail["fields"] == []
    assert client.get("/api/agent/status").json()["queue"] == [applied]
    worker._stopping.clear()  # pylint: disable=protected-access


def test_delete_account_mid_run(client, app, applied, monkeypatch):
    seed_fake_form_answers(app)
    worker = app.state.worker
    original = worker._on_event  # pylint: disable=protected-access

    def wipe_after_first_fill(ctx, submit, kind, data):
        original(ctx, submit, kind, data)
        if kind == "filled":
            assert client.delete("/api/account").status_code == 204
    monkeypatch.setattr(worker, "_on_event", wipe_after_first_fill)
    worker.run_next()
    assert app.state.store.read("jobs") == []


@pytest.mark.parametrize("form_field,guess,expected", [
    (FormField("q", "Pronouns?", "select", True, ["She", "He", "They"]), None,
     ("confirm", ["She", "He", "They"], "Nothing in your profile or Answer bank answers this. "
      "Pick one (She, He, They), or reply in your own words.")),
    (FormField("q", "Year?", "select", True, [str(y) for y in range(2020, 2027)]), None,
     ("confirm", [str(y) for y in range(2020, 2027)], "Nothing in your profile or Answer bank "
      "answers this. Pick one (2020, 2021, 2022, 2023, 2024 and 2 more), or reply in your own "
      "words.")),
    (FormField("q", "State?", "select", True, [f"S{i}" for i in range(13)]),
     FieldAnswer("S1", "claude", 40, ""),
     ("confirm", None, "Reply with the option you want; it has to match one on the form.")),
    (FormField("q", "City?", "text", True), FieldAnswer("", "claude", 0, ""),
     ("confirm", None, "Nothing in your profile or Answer bank answers this. What should I "
      "enter?")),
])
def test_make_question_variants(form_field, guess, expected):
    question, internal = make_question("job-9", 3, form_field, guess)
    assert question["id"] == "q-job-9-3"
    assert (question["type"], question["pickOptions"], question["messages"][0]["text"]) == expected
    assert question["placeholder"] == "e.g. the right answer"
    assert question["defaultScope"] == "all" and question["draft"] is None
    assert internal == {"fieldKey": "q", "label": form_field.label, "kind": form_field.kind,
                        "options": form_field.options}
