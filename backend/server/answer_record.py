"""One saved answer in the Answer bank, and the categories answers are filed under."""
from dataclasses import dataclass, field
from enum import Enum

ANSWER_CATEGORIES = ["Eligibility", "Education", "Logistics", "Pay", "Experience", "Self-ID"]

# Keyword checks, in order; the first category with a matching keyword wins
_CATEGORY_KEYWORDS = [
    (("sponsor", "authoriz", "eligib", "legally", "citizen", "clearance"), "Eligibility"),
    (("school", "degree", "gpa", "graduat", "university", "major"), "Education"),
    (("salary", "pay", "compensation"), "Pay"),
    (("gender", "race", "ethnic", "veteran", "disabilit", "pronoun"), "Self-ID"),
    (("start", "relocat", "location", "office", "on-site", "onsite", "remote", "hear about",
      "available"), "Logistics"),
]


class AnswerOrigin(str, Enum):
    """How an answer got into the bank."""

    ONBOARDING = "onboarding"
    REPLY = "reply"
    MANUAL = "manual"
    IMPORT = "import"


def guess_category(label: str) -> str:
    """Return the Answer-bank category for a question by keyword; "Experience" if none match."""
    text = (label or "").lower()
    for keywords, category in _CATEGORY_KEYWORDS:
        if any(word in text for word in keywords):
            return category
    return "Experience"


def clean_company(company: str | None) -> str | None:
    """Return the company name trimmed, or None for no company (an answer for every company)."""
    company = (company or "").strip()
    return company or None


def same_company(first: str | None, second: str | None) -> bool:
    """Return True when two company names are the same, ignoring case and spaces."""
    return (first or "").strip().casefold() == (second or "").strip().casefold()


@dataclass
class AnswerRecord:  # pylint: disable=too-many-instance-attributes  # one per stored JSON key
    """A saved answer: the API Answer plus when it was made, changed, and where it came from."""

    id: str  # pylint: disable=invalid-name  # the API's own key
    category: str
    question: str
    answer: str
    source: str = ""
    company: str | None = None
    times_used: int = 0
    last_used_at: str | None = None
    also_matches: list[dict] = field(default_factory=list)
    used_on: list[dict] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    origin: AnswerOrigin = AnswerOrigin.IMPORT

    @classmethod
    def from_json(cls, key: str, value) -> "AnswerRecord | None":
        """Build a record from what's stored under `key`, or None for a value to ignore.

        A plain string (as the onboarding module saves it) reads as an imported answer
        whose id and question are the key.
        """
        if isinstance(value, str):
            return cls(id=key, category=guess_category(key), question=key, answer=value,
                       source="Imported")
        if not isinstance(value, dict):
            return None
        question = str(value.get("question") or key)
        category = value.get("category")
        origin = value.get("origin")
        return cls(
            id=key,
            category=category if category in ANSWER_CATEGORIES else guess_category(question),
            question=question,
            answer=str(value.get("answer") if value.get("answer") is not None else ""),
            source=str(value.get("source") or ""),
            company=clean_company(value.get("company")),
            times_used=int(value.get("timesUsed") or 0),
            last_used_at=value.get("lastUsedAt"),
            also_matches=list(value.get("alsoMatches") or []),
            used_on=list(value.get("usedOn") or []),
            created_at=value.get("createdAt"),
            updated_at=value.get("updatedAt"),
            origin=AnswerOrigin(origin) if origin in _ORIGIN_VALUES else AnswerOrigin.IMPORT,
        )

    def to_json(self) -> dict:
        """Return the record as the bank file stores it."""
        return {**self._shared_json(), "createdAt": self.created_at,
                "updatedAt": self.updated_at, "origin": self.origin.value}

    def to_api(self, saved_recently: bool) -> dict:
        """Return the API Answer (exactly the keys the frontend reads)."""
        return {**self._shared_json(), "savedRecently": saved_recently}

    def _shared_json(self) -> dict:
        """Return the keys the stored record and the API Answer have in common."""
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "source": self.source,
            "company": self.company,
            "timesUsed": self.times_used,
            "lastUsedAt": self.last_used_at,
            "alsoMatches": self.also_matches,
            "usedOn": self.used_on,
        }


_ORIGIN_VALUES = tuple(origin.value for origin in AnswerOrigin)
