"""Mirrors setup's common answers into the Answer bank as `onb-<key>` records."""
from datetime import date

from onboarding.onboarding_questions import load_questions
from server import self_id
from server.answer_bank import AnswerBank, guess_category
from server.answer_record import AnswerOrigin

COMMON_QUESTION_KEYS = [
    "workAuthorized", "needsSponsorship", "graduation", "earliestStart", "relocate",
    "locations", "expectedPay", "familyEmployers", *self_id.KEYS,
]
# Records older setups wrote, deleted on the next save
RETIRED_KEYS = [self_id.LEGACY_KEY]
SOURCE = "Onboarding · common questions"
ORIGIN = AnswerOrigin.ONBOARDING.value
_CHOICE_KEYS = ("workAuthorized", "needsSponsorship", "relocate")
_CHOICES = ("Yes", "No", "Depends")
_FREE_TEXT_KEYS = ("graduation", "expectedPay")


def record_id(key: str) -> str:
    """Return the Answer-bank id of a common question's record."""
    return f"onb-{key}"


def long_date(value: str | None) -> str:
    """Return "2027-06-01" as "June 1, 2027"; anything that isn't YYYY-MM-DD comes back as is."""
    if not value:
        return ""
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{day:%B} {day.day}, {day.year}"


def _listed(values: list | None) -> list[str]:
    """Return the non-blank items of a list, trimmed."""
    return [str(value).strip() for value in values or [] if str(value).strip()]


def _choice_text(value) -> str | None:
    """Return a Yes / No / Depends answer, or None."""
    return value if value in _CHOICES else None


def _free_text(value) -> str | None:
    """Return the trimmed text, or None when blank."""
    return (value or "").strip() or None


def _family_text(value) -> str:
    """Return the family-employers answer: "No", or the employers to check."""
    names = _listed(value)
    return f"Possibly: {', '.join(names)}" if names else "No"


# key -> how its stored value reads as a bank answer
_FORMATTERS = {
    **{key: _choice_text for key in _CHOICE_KEYS},
    **{key: _free_text for key in _FREE_TEXT_KEYS},
    "earliestStart": lambda value: long_date(value) or None,
    "locations": lambda value: "; ".join(_listed(value)) or None,
    "familyEmployers": _family_text,
}


def answer_text(key: str, common: dict) -> str | None:
    """Return the bank answer for one common question, or None when there is nothing to save."""
    value = common.get(key)
    if key == "race":
        return self_id.answer_wording(key, self_id.effective_race(common))
    if key in _FORMATTERS:
        return _FORMATTERS[key](value)
    if key in self_id.VALUES:
        return self_id.answer_wording(key, value)
    return None


def catalog() -> dict[str, tuple[str, str]]:
    """Return key -> (question wording, category) from onboarding_questions.json."""
    questions = load_questions()
    out = {}
    for key in COMMON_QUESTION_KEYS:
        entry = questions.get(key) or [key, key]
        wording = entry[0]
        category = entry[2] if len(entry) > 2 else guess_category(wording)
        out[key] = (wording, category)
    return out


def sync_bank(bank: AnswerBank, common: dict) -> None:
    """Upsert `onb-<key>` for each answered, non-skipped key and delete the rest.

    The sync is one way: editing an `onb-*` answer in the bank doesn't change the common
    answers, and saving setup again overwrites the `onb-*` records.
    """
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
