"""Setup's common answers -> `onb-<key>` Answer-bank records (spec 2.5).

`PUT /common-answers` stores common_answers.json and calls `sync_bank`. The wording and category
of each record come from Konefal's OnboardingQuestions.json catalog. The sync is one-way: editing
an `onb-*` answer in the Answer bank doesn't change the common answers, and saving setup again
overwrites the `onb-*` records.

Self-identification is five questions (server/self_id.py), each its own `onb-*` record.
"""
from datetime import date

from server import konefal, self_id
from server.answer_bank import AnswerBank, guess_category

COMMON_QUESTION_KEYS = [
    "workAuthorized", "needsSponsorship", "graduation", "earliestStart", "relocate",
    "locations", "expectedPay", "familyEmployers", *self_id.KEYS,
]
# Records older setups wrote, deleted on the next save
RETIRED_KEYS = [self_id.LEGACY_KEY]
SOURCE = "Onboarding · common questions"
ORIGIN = "onboarding"


def record_id(key: str) -> str:
    return f"onb-{key}"


def long_date(value: str | None) -> str:
    """"2027-06-01" -> "June 1, 2027". Anything that isn't YYYY-MM-DD comes back unchanged."""
    if not value:
        return ""
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{day:%B} {day.day}, {day.year}"


def answer_text(key: str, common: dict) -> str | None:
    """The bank answer for one common question, or None when there is nothing to save."""
    value = common.get(key)
    if key in ("workAuthorized", "needsSponsorship", "relocate"):
        return value if value in ("Yes", "No", "Depends") else None
    if key == "graduation":
        return (value or "").strip() or None
    if key == "earliestStart":
        return long_date(value) or None
    if key == "locations":
        places = [str(p).strip() for p in value or [] if str(p).strip()]
        return "; ".join(places) or None
    if key == "expectedPay":
        return (value or "").strip() or None
    if key == "familyEmployers":
        names = [str(n).strip() for n in value or [] if str(n).strip()]
        return f"Possibly: {', '.join(names)}" if names else "No"
    if key == "race":
        return self_id.answer_wording(key, self_id.effective_race(common))
    if key in self_id.VALUES:
        return self_id.answer_wording(key, value)
    return None


def catalog() -> dict[str, tuple[str, str]]:
    """key -> (question wording, category) from OnboardingQuestions.json."""
    questions = konefal.onboarding_questions()
    out = {}
    for key in COMMON_QUESTION_KEYS:
        entry = questions.get(key) or [key, key]
        wording = entry[0]
        category = entry[2] if len(entry) > 2 else guess_category(wording)
        out[key] = (wording, category)
    return out


def sync_bank(bank: AnswerBank, common: dict) -> None:
    """Upserts `onb-<key>` for each answered, non-skipped key; deletes the rest."""
    skipped = set(common.get("skipped") or [])
    wording = catalog()
    with bank.store.lock:
        for key in RETIRED_KEYS:
            bank.delete(record_id(key))
        for key in COMMON_QUESTION_KEYS:
            text = None if key in skipped else answer_text(key, common)
            if text is None:
                bank.delete(record_id(key))
                continue
            question, category = wording[key]
            bank.put(record_id(key), question=question, answer=text, category=category,
                     origin=ORIGIN, source=SOURCE)
