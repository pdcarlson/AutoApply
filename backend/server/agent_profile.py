"""Projects the stored profile, common answers and Answer bank into the agent's `Profile`."""
import re
from datetime import datetime

from agent.applicant.profile import Profile, SavedAnswer
from server import self_id
from server.answer_bank import AnswerBank
from server.common_answers import long_date
from server.names import NAME_KEYS
from server.store import Store

DEFAULT_COUNTRY = "United States"
# How each Experience kind is named in the agent's facts, so it can tell a job from a club role.
EXPERIENCE_FACT_LABELS = {"work": "Work experience", "leadership": "Leadership",
                          "volunteer": "Volunteer work", "activity": "Activity"}


def build_agent_profile(store: Store, bank: AnswerBank,
                        company: str | None) -> tuple[Profile, dict[str, str]]:
    """Return the agent Profile for one run at `company`, and {normalized wording: answer id}.

    The Profile lives only in memory for that run; it is never saved.
    """
    profile = store.read("profile")
    common = _answered(store.read("common_answers") or {})
    answers, ids = bank.projection(company)
    agent_profile = Profile(
        **_contact(store, profile),
        **_current_job(profile),
        **_education(profile, common),
        **_eligibility(common),
        **_self_id(common),
        answers=[SavedAnswer(answer.question, answer.answer) for answer in answers],
        extra_facts=_extra_facts(profile, common),
    )
    return agent_profile, ids


def month_year(value: str | None) -> str:
    """Return "2027-05" as "May 2027"; anything else comes back unchanged."""
    if not value:
        return ""
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", value.strip())
    if not match:
        return value
    try:
        return datetime(int(match.group(1)), int(match.group(2)), 1).strftime("%B %Y")
    except ValueError:
        return value


def _answered(common: dict) -> dict:
    """Return the common answers with every skipped question set to None."""
    skipped = set(common.get("skipped") or [])
    return {key: (None if key in skipped else value) for key, value in common.items()}


def _yes_no(value) -> bool | None:
    """Return True for "Yes", False for "No", and None for anything else."""
    return {"Yes": True, "No": False}.get(value)


def _contact(store: Store, profile: dict) -> dict:
    """Return the Profile's name, contact, link and resume fields."""
    first, middle, last = (" ".join(str(profile.get(key) or "").split()) for key in NAME_KEYS)
    links = {link.get("id"): link.get("url", "") for link in profile.get("links") or []}
    resume = profile.get("_resumePath") or ""
    resume_path = store.path(*resume.split("/")) if resume else None
    return {
        "first_name": first, "middle_name": middle, "last_name": last,
        "email": profile.get("email", ""), "phone": profile.get("phone", ""),
        "city": profile.get("city", ""), "state": profile.get("state", ""),
        "country": profile.get("country") or DEFAULT_COUNTRY,
        "linkedin": links.get("linkedin", ""), "github": links.get("github", ""),
        "website": links.get("web", ""),
        "resume_path": (str(resume_path.resolve())
                        if resume_path and resume_path.is_file() else ""),
    }


def _current_job(profile: dict) -> dict:
    """Return the current employer and title: paid work only, never a club or volunteer role."""
    work = [item for item in profile.get("experience") or []
            if (item.get("kind") or "work") == "work"]
    job = next((item for item in work if item.get("current")), work[0] if work else {})
    return {"current_company": job.get("org", ""), "current_title": job.get("title", "")}


def _education(profile: dict, common: dict) -> dict:
    """Return the school fields, from the first education entry."""
    school = (profile.get("education") or [{}])[0]
    return {
        "school": school.get("school", ""), "degree": school.get("degreeType", ""),
        "major": school.get("major", ""), "gpa": school.get("gpa", ""),
        "graduation": (common.get("graduation") or "").strip() or month_year(school.get("end")),
        "school_start": month_year(school.get("start")),
    }


def _eligibility(common: dict) -> dict:
    """Return the start date, work authorization, sponsorship and relocation answers."""
    return {
        "earliest_start": long_date(common.get("earliestStart")),
        "work_authorized_us": _yes_no(common.get("workAuthorized")),
        "needs_sponsorship": _yes_no(common.get("needsSponsorship")),
        "willing_to_relocate": _yes_no(common.get("relocate")),
    }


def _self_id(common: dict) -> dict:
    """Return the voluntary self-ID answers; each question without one is asked."""
    return {
        "eeo": "ask",
        "gender": common.get("gender") or "",
        "hispanic_latino": common.get("hispanicLatino") or "",
        "race": self_id.effective_race(common) or "",
        "veteran": common.get("veteran") or "",
        "disability": common.get("disability") or "",
    }


def _span(start: str, end: str, is_current: bool) -> str:
    """Return a date range like "June 2025–Present"."""
    start, end = month_year(start), "Present" if is_current else month_year(end)
    return f"{start}–{end}" if start and end else start or end


def _extra_facts(profile: dict, common: dict) -> list[str]:
    """Return the extra lines Claude reads: skills, places, pay, custom fields and history."""
    facts = []
    if profile.get("skills"):
        facts.append("Skills: " + ", ".join(profile["skills"]))
    places = [place for place in common.get("locations") or [] if str(place).strip()]
    if places:
        facts.append("Wants to work in: " + "; ".join(places))
    if common.get("relocate") == "Depends":
        facts.append("Relocation: depends on the role")
    if (common.get("expectedPay") or "").strip():
        facts.append(f"Expected pay: {common['expectedPay'].strip()} "
                     "(only give it when a number is required)")
    employers = [name for name in common.get("familyEmployers") or [] if str(name).strip()]
    if employers:
        facts.append("Companies the applicant or family members worked for: "
                     + ", ".join(employers))
    for item in profile.get("custom") or []:
        if item.get("label") and item.get("value"):
            facts.append(f"{item['label']}: {item['value']}")
    return facts + _history_facts(profile)


def _history_facts(profile: dict) -> list[str]:
    """Return one line per experience entry and project."""
    facts = []
    for item in profile.get("experience") or []:
        head = " at ".join(filter(None, [item.get("title"), item.get("org")]))
        when = _span(item.get("start", ""), item.get("end", ""), bool(item.get("current")))
        label = EXPERIENCE_FACT_LABELS.get(item.get("kind") or "work", "Experience")
        if head:
            facts.append(f"{label}: {head}" + (f", {when}" if when else ""))
    for item in profile.get("projects") or []:
        if item.get("name"):
            tech = f" ({item['tech']})" if item.get("tech") else ""
            detail = f": {item['detail']}" if item.get("detail") else ""
            facts.append(f"Project: {item['name']}{tech}{detail}")
    return facts
