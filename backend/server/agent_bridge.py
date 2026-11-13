"""Glue between the server's records and the agent package (spec 2.6, 2.9, WP4 scope).

- `build_agent_profile(store, bank, company)` projects the frontend Profile, the common answers
  and the bank entries that apply to `company` into an in-memory agent `Profile`. It is never
  saved.
- `make_form(job, config)` builds the agent form for a job record, routing the fake Greenhouse
  posting to `backend/agent/tests/fake_forms` when FAKE_GREENHOUSE is on.
- `cached_claude(store, job_id)` is the `ask_claude` the Answerer gets: it remembers Claude's
  guesses in `job.internal.claudeCache`, so re-runs after a question are free and stable.
- `SourceMap` turns the agent's (label, value, source, confidence) into the API `FilledField`.
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent.answers import claude as agent_claude
from agent.applicant.profile import Profile, SavedAnswer, normalize
from agent.forms import form_for
from agent.forms.form_field import FieldAnswer, FormField
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink
from server import self_id
from server.answer_bank import AnswerBank
from server.common_answers import long_date
from server.config import BACKEND_DIR, Config
from server.names import NAME_KEYS
from server.store import Store, parse_iso

log = logging.getLogger(__name__)

FAKE_FORMS = BACKEND_DIR / "agent" / "tests" / "fake_forms"
FAKE_COMPANY = "fakecompany"
# Only these exact test postings map to the local fake form. Any other link, including
# fakecompany with another job id, is treated as a real Greenhouse posting.
FAKE_JOB_IDS = frozenset({"1001", "1002"})
DEFAULT_COUNTRY = "United States"

# Looked up at call time, so tests can monkeypatch `server.agent_bridge.ask_claude`.
ask_claude = agent_claude.ask_claude


# ----- links and forms -----

def link_to_dict(link: JobLink) -> dict:
    return {"url": link.url, "site": link.site, "company": link.company, "job_id": link.job_id,
            "pasted": link.pasted}


def link_of(job: dict) -> JobLink:
    return JobLink(**job["internal"]["link"])


def is_fake(link: JobLink, config: Config) -> bool:
    return bool(config.fake_greenhouse) and link.site == "greenhouse" \
        and link.company.lower() == FAKE_COMPANY and link.job_id in FAKE_JOB_IDS


def fake_job_data() -> dict:
    return json.loads((FAKE_FORMS / "greenhouse_api.json").read_text(encoding="utf-8"))


def make_form(job: dict, config: Config):
    """The agent form for a job record (`internal.link`, `internal.jobData`).

    Raises agent UnsupportedLink for sites the agent can't fill (Ashby, Lever). The fake
    Greenhouse posting never touches the network: its API payload and page are local files.
    """
    link = link_of(job)
    if is_fake(link, config):
        return GreenhouseForm(link, job_data=fake_job_data(),
                              url=(FAKE_FORMS / "greenhouse_form.html").resolve().as_uri())
    form = form_for(link)
    cached = (job.get("internal") or {}).get("jobData")
    if cached is not None:
        form.job_data = cached
    return form


# ----- profile projection (spec 2.6) -----

def _yes_no(value) -> bool | None:
    return {"Yes": True, "No": False}.get(value)


def month_year(value: str | None) -> str:
    """"2027-05" -> "May 2027". Anything else comes back unchanged."""
    if not value:
        return ""
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", value.strip())
    if not match:
        return value
    try:
        return datetime(int(match.group(1)), int(match.group(2)), 1).strftime("%B %Y")
    except ValueError:
        return value


def _span(start: str, end: str, current: bool) -> str:
    start, end = month_year(start), "Present" if current else month_year(end)
    return f"{start}–{end}" if start and end else start or end


def _extra_facts(profile: dict, common: dict) -> list[str]:
    facts = []
    if profile.get("skills"):
        facts.append("Skills: " + ", ".join(profile["skills"]))
    places = [p for p in common.get("locations") or [] if str(p).strip()]
    if places:
        facts.append("Wants to work in: " + "; ".join(places))
    if common.get("relocate") == "Depends":
        facts.append("Relocation: depends on the role")
    if (common.get("expectedPay") or "").strip():
        facts.append(f"Expected pay: {common['expectedPay'].strip()} "
                     "(only give it when a number is required)")
    employers = [e for e in common.get("familyEmployers") or [] if str(e).strip()]
    if employers:
        facts.append("Companies the applicant or family members worked for: "
                     + ", ".join(employers))
    for item in profile.get("custom") or []:
        if item.get("label") and item.get("value"):
            facts.append(f"{item['label']}: {item['value']}")
    for item in profile.get("experience") or []:
        head = " at ".join(filter(None, [item.get("title"), item.get("org")]))
        when = _span(item.get("start", ""), item.get("end", ""), bool(item.get("current")))
        if head:
            facts.append(f"Experience: {head}" + (f", {when}" if when else ""))
    for item in profile.get("projects") or []:
        if item.get("name"):
            tech = f" ({item['tech']})" if item.get("tech") else ""
            detail = f": {item['detail']}" if item.get("detail") else ""
            facts.append(f"Project: {item['name']}{tech}{detail}")
    return facts


def build_agent_profile(store: Store, bank: AnswerBank,  # pylint: disable=too-many-locals
                        company: str | None) -> tuple[Profile, dict[str, str]]:
    """(agent Profile for one run, {normalize(wording): answer id}) for `company`."""
    profile = store.read("profile")
    common = store.read("common_answers") or {}
    skipped = set(common.get("skipped") or [])
    common = {k: (None if k in skipped else v) for k, v in common.items()}

    first, middle, last = (" ".join(str(profile.get(key) or "").split()) for key in NAME_KEYS)
    links = {link.get("id"): link.get("url", "") for link in profile.get("links") or []}
    experience = profile.get("experience") or []
    job = next((e for e in experience if e.get("current")), experience[0] if experience else {})
    school = (profile.get("education") or [{}])[0]
    resume = profile.get("_resumePath") or ""
    resume_path = store.path(*resume.split("/")) if resume else None

    answers, ids = bank.projection(company)
    agent_profile = Profile(
        first_name=first,
        middle_name=middle,
        last_name=last,
        email=profile.get("email", ""),
        phone=profile.get("phone", ""),
        city=profile.get("city", ""),
        state=profile.get("state", ""),
        country=profile.get("country") or DEFAULT_COUNTRY,
        linkedin=links.get("linkedin", ""),
        github=links.get("github", ""),
        website=links.get("web", ""),
        resume_path=str(resume_path.resolve()) if resume_path and resume_path.is_file() else "",
        current_company=job.get("org", ""),
        current_title=job.get("title", ""),
        school=school.get("school", ""),
        degree=school.get("degreeType", ""),
        major=school.get("major", ""),
        gpa=school.get("gpa", ""),
        graduation=(common.get("graduation") or "").strip() or month_year(school.get("end")),
        school_start=month_year(school.get("start")),
        earliest_start=long_date(common.get("earliestStart")),
        work_authorized_us=_yes_no(common.get("workAuthorized")),
        needs_sponsorship=_yes_no(common.get("needsSponsorship")),
        willing_to_relocate=_yes_no(common.get("relocate")),
        eeo="ask",  # each self-ID question has its own answer, or is asked
        gender=common.get("gender") or "",
        hispanic_latino=common.get("hispanicLatino") or "",
        race=self_id.effective_race(common) or "",
        veteran=common.get("veteran") or "",
        disability=common.get("disability") or "",
        answers=[SavedAnswer(a.question, a.answer) for a in answers],
        extra_facts=_extra_facts(profile, common),
    )
    return agent_profile, ids


# ----- Claude, cached per job -----

def cached_claude(store: Store, job_id: str):
    """An `ask_claude(field, facts)` that reads and writes `job.internal.claudeCache`.

    A "couldn't help" result (empty value, confidence 0: no API key, an API error) isn't
    cached, so adding a key later or a passing outage doesn't stick to the job.
    """
    def ask(form_field: FormField, facts: str) -> FieldAnswer:
        with store.tx() as db:
            job = next((j for j in db.jobs if j.get("id") == job_id), None)
            hit = ((job or {}).get("internal") or {}).get("claudeCache", {}).get(form_field.key)
            if hit is not None:
                return FieldAnswer(hit.get("value", ""), "claude", int(hit.get("confidence", 0)),
                                   hit.get("reason", ""))
        guess = ask_claude(form_field, facts)  # outside the lock: this can take seconds
        if guess.value or guess.confidence:
            with store.tx() as db:
                job = next((j for j in db.jobs if j.get("id") == job_id), None)
                if job is not None:
                    job["internal"].setdefault("claudeCache", {})[form_field.key] = {
                        "value": guess.value, "confidence": guess.confidence,
                        "reason": guess.reason}
        return guess
    return ask


def no_claude(_form_field: FormField, _facts: str) -> FieldAnswer:
    """Never calls Claude: the quick dry answer pass in POST /jobs, and runs with Claude off."""
    return FieldAnswer("", "claude", 0, "Not asked.")


# ----- FilledField mapping -----

def short_date(text: str | None) -> str:
    """ISO timestamp -> "Oct 16" (local time); "" when missing."""
    moment = parse_iso(text)
    if moment is None:
        return ""
    local = moment.astimezone()
    return f"{local:%b} {local.day}"


@dataclass
class SourceMap:
    """Maps the agent's answer sources to the API's `source` / `sourceKind` for one run."""

    ids: dict[str, str]  # normalize(wording) -> answer id, from build_agent_profile
    records: dict[str, dict]  # answer id -> bank record

    @classmethod
    def build(cls, bank: AnswerBank, ids: dict[str, str]) -> "SourceMap":
        return cls(ids, {r["id"]: r for r in bank.records() if r["id"] in set(ids.values())})

    def record_for(self, label: str) -> dict | None:
        answer_id = self.ids.get(normalize(label))
        return self.records.get(answer_id) if answer_id else None

    def describe(self, label: str, source: str) -> tuple[str, str]:
        """(source text, sourceKind) for one filled field."""
        if source == "profile":
            return "Profile", "profile"
        if source == "claude":
            return "Claude, from your profile", "other"
        record = self.record_for(label)
        if record is not None and record["id"].startswith("onb-"):
            return "Common questions", "common_questions"
        if record is not None and record.get("origin") == "reply":
            day = short_date(record.get("updatedAt") or record.get("createdAt"))
            return (f"You answered · {day}" if day else "You answered"), "you"
        return "Answer bank", "answer_bank"

    def filled_field(self, form_field: FormField | None, label: str, value: str, source: str,
                     confidence: int) -> dict:
        """The API `FilledField`. File fields show the file name, not the path."""
        text, kind = self.describe(label, source)
        is_file = form_field is not None and form_field.kind == "file"
        return {
            "label": label,
            "value": Path(value).name if is_file and value else value,
            "source": text,
            "sourceKind": kind,
            "confidence": 100 if source == "profile" else int(confidence),
        }

    def from_answered(self, answered: list) -> list[dict]:
        """FilledFields for (FormField, FieldAnswer) pairs, e.g. the planned fields."""
        return [self.filled_field(f, f.label, a.value, a.source, a.confidence)
                for f, a in answered]
