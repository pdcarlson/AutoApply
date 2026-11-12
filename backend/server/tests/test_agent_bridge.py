"""agent_bridge: the agent Profile projection, make_form, Claude cache, FilledField mapping."""
import urllib.request

import pytest

from agent.forms.form_field import FieldAnswer, FormField
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink, UnsupportedLink
from server import agent_bridge
from server.agent_bridge import (SourceMap, build_agent_profile, cached_claude, link_to_dict,
                                 make_form, month_year)
from server.tests.job_helpers import FAKE_URL, SPONSORSHIP


def _job(url, job_data=None):
    return {"id": "job-1", "company": "Fake Company",
            "internal": {"link": link_to_dict(JobLink.parse(url)), "jobData": job_data,
                         "claudeCache": {}}}


def _set_profile(app, **changes):
    with app.state.store.tx() as db:
        db.profile.update(changes)


def test_fake_greenhouse_form_is_local(app, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    form = make_form(_job(FAKE_URL), app.state.config)
    assert isinstance(form, GreenhouseForm)
    assert form.form_url().startswith("file:///")
    assert form.form_url().endswith("agent/tests/fake_forms/greenhouse_form.html")
    assert len(form.read_fields()) == 11


def test_fake_routing_needs_the_flag(app):
    app.state.config.fake_greenhouse = False
    form = make_form(_job(FAKE_URL, job_data={"title": "Cached", "questions": []}),
                     app.state.config)
    assert form.url is None  # the real embed page
    assert form.job_data == {"title": "Cached", "questions": []}  # no fetch at run time


def test_other_sites_are_unsupported(app):
    with pytest.raises(UnsupportedLink):
        make_form(_job("https://jobs.ashbyhq.com/acme/123"), app.state.config)


def test_profile_projection(app):
    store = app.state.store
    store.dir("resume")
    store.path("resume", "cv.pdf").write_bytes(b"%PDF-1.4")
    _set_profile(
        app, name="Ada  Byron King", email="ada@example.com", phone="555", city="Troy",
        state="NY", country="", _resumePath="resume/cv.pdf",
        links=[{"id": "web", "url": "https://ada.dev"}, {"id": "linkedin", "url": "li/ada"},
               {"id": "github", "url": "gh/ada"}],
        education=[{"school": "RPI", "degreeType": "B.S.", "major": "CS", "gpa": "3.9",
                    "end": "2027-05"}],
        experience=[{"title": "Intern", "org": "Old Co", "start": "2025-06", "end": "2025-08",
                     "current": False},
                    {"title": "Engineer", "org": "Now Co", "start": "2026-01", "end": "",
                     "current": True}],
        projects=[{"name": "Planner", "tech": "React", "detail": "Course planner"}],
        skills=["Python", "SQL"], custom=[{"id": "cf-1", "label": "Pronouns", "value": "she/her"}])
    with store.tx() as db:
        db.common_answers.update(workAuthorized="Yes", needsSponsorship=None, relocate="Depends",
                                 earliestStart="2027-06-01", expectedPay="$40/hr",
                                 familyEmployers=["Acme"], selfId="ask",
                                 locations=["Remote (US)", "NYC"], skipped=["workAuthorized"])

    profile, _ids = build_agent_profile(store, app.state.answer_bank, "Fake Company")
    assert (profile.first_name, profile.last_name) == ("Ada", "Byron King")
    assert profile.country == "United States"
    assert (profile.website, profile.linkedin, profile.github) == ("https://ada.dev", "li/ada",
                                                                   "gh/ada")
    assert profile.resume_path == str(store.path("resume", "cv.pdf").resolve())
    assert (profile.current_company, profile.current_title) == ("Now Co", "Engineer")
    assert (profile.school, profile.degree, profile.major, profile.gpa) == ("RPI", "B.S.", "CS",
                                                                            "3.9")
    assert profile.graduation == "May 2027"
    assert profile.earliest_start == "June 1, 2027"
    assert profile.work_authorized_us is None  # skipped
    assert profile.needs_sponsorship is None and profile.willing_to_relocate is None
    assert profile.eeo == "ask"
    facts = profile.facts()
    assert "Authorized to work in the United States: Unknown (ask the applicant)" in facts
    for line in ["Skills: Python, SQL", "Wants to work in: Remote (US); NYC",
                 "Relocation: depends on the role",
                 "Expected pay: $40/hr (only give it when a number is required)",
                 "Companies the applicant or family members worked for: Acme",
                 "Pronouns: she/her", "Experience: Engineer at Now Co, January 2026–Present",
                 "Project: Planner (React): Course planner"]:
        assert line in profile.extra_facts


def test_profile_defaults_and_missing_resume(app):
    with app.state.store.tx() as db:
        db.common_answers.update(workAuthorized="No", needsSponsorship="Yes", relocate="Yes",
                                 graduation="Dec 2026")
    _set_profile(app, _resumePath="resume/gone.pdf",
                 education=[{"school": "RPI", "end": "2027-05"}])
    profile, _ids = build_agent_profile(app.state.store, app.state.answer_bank, None)
    assert (profile.first_name, profile.last_name) == ("Demo", "User")
    assert profile.resume_path == ""  # the file isn't there
    assert profile.work_authorized_us is False and profile.needs_sponsorship is True
    assert profile.willing_to_relocate is True and profile.eeo == "decline"
    assert profile.graduation == "Dec 2026"  # the common answer wins over education end


def test_bank_projection_is_per_company(app):
    bank = app.state.answer_bank
    bank.upsert_by_question("Why us?", "Global", origin="manual")
    bank.upsert_by_question("Why us?", "For Fake", company="Fake Company", origin="reply")
    bank.upsert_by_question("Why us?", "For Other", company="Other", origin="reply")
    profile, ids = build_agent_profile(app.state.store, bank, "Fake Company")
    assert profile.saved_answer("why us?") == "For Fake"
    assert len(ids) == 1
    profile, _ids = build_agent_profile(app.state.store, bank, "Third")
    assert profile.saved_answer("Why us?") == "Global"


def test_source_map(app):
    bank = app.state.answer_bank
    bank.put("onb-relocate", question="Are you willing to relocate?", answer="Yes",
             category="Logistics", origin="onboarding", source="Onboarding")
    bank.upsert_by_question(SPONSORSHIP, "No", origin="reply", source="x")
    bank.upsert_by_question("How did you hear about this job?", "LinkedIn", origin="manual")
    _profile, ids = build_agent_profile(app.state.store, bank, "Fake Company")
    sources = SourceMap.build(bank, ids)

    resume = FormField("resume", "Resume/CV", "file")
    assert sources.filled_field(resume, "Resume/CV", "C:/data/resume/cv.pdf", "profile", 100) == {
        "label": "Resume/CV", "value": "cv.pdf", "source": "Profile", "sourceKind": "profile",
        "confidence": 100}
    assert sources.describe("Are you willing to relocate?", "saved") == ("Common questions",
                                                                         "common_questions")
    text, kind = sources.describe(SPONSORSHIP, "saved")
    assert kind == "you" and text.startswith("You answered · ")
    assert sources.describe("How did you hear about this job?", "saved") == ("Answer bank",
                                                                            "answer_bank")
    claude = sources.filled_field(None, "Why?", "Because", "claude", 93)
    assert (claude["source"], claude["sourceKind"], claude["confidence"]) == (
        "Claude, from your profile", "other", 93)


def test_cached_claude(app, monkeypatch):
    with app.state.store.tx() as db:
        db.jobs.append(_job(FAKE_URL))
    calls = []

    def fake_ask(form_field, _facts):
        calls.append(form_field.key)
        if form_field.key == "known":
            return FieldAnswer("Yes", "claude", 70, "guess")
        return FieldAnswer("", "claude", 0, "No Anthropic API key set.")
    monkeypatch.setattr(agent_bridge, "ask_claude", fake_ask)
    ask = cached_claude(app.state.store, "job-1")
    known, unknown = FormField("known", "Known?", "text"), FormField("unknown", "Unknown?", "text")
    assert ask(known, "facts") == FieldAnswer("Yes", "claude", 70, "guess")
    assert ask(known, "facts") == FieldAnswer("Yes", "claude", 70, "guess")
    ask(unknown, "facts")
    ask(unknown, "facts")
    assert calls == ["known", "unknown", "unknown"]  # "couldn't help" isn't cached
    cache = app.state.store.read("jobs")[0]["internal"]["claudeCache"]
    assert cache == {"known": {"value": "Yes", "confidence": 70, "reason": "guess"}}


def test_month_year():
    assert month_year("2027-05") == "May 2027"
    assert month_year("May 2027") == "May 2027"
    assert month_year("") == ""
    assert month_year("2027-13") == "2027-13"
