"""Says where each filled answer came from, as the API's `FilledField` shows it."""
from dataclasses import dataclass
from pathlib import Path

from agent.applicant.profile import normalize
from agent.forms.form_field import FieldAnswer, FormField
from server.answer_bank import AnswerBank
from server.store import parse_iso

# Answers saved by the setup questions have ids that start with this.
COMMON_ANSWER_PREFIX = "onb-"


def short_date(text: str | None) -> str:
    """Return an ISO timestamp as "Oct 16" (local time), or "" when missing."""
    moment = parse_iso(text)
    if moment is None:
        return ""
    local = moment.astimezone()
    return f"{local:%b} {local.day}"


@dataclass
class SourceMap:
    """Maps the agent's answer sources to the API's `source` and `sourceKind` for one run."""

    ids: dict[str, str]  # normalized wording -> answer id, from build_agent_profile
    records: dict[str, dict]  # answer id -> Answer bank record

    @classmethod
    def build(cls, bank: AnswerBank, ids: dict[str, str]) -> "SourceMap":
        """Build the map for the answers one run's profile was given."""
        wanted = set(ids.values())
        return cls(ids, {record["id"]: record for record in bank.records()
                         if record["id"] in wanted})

    def record_for(self, label: str) -> dict | None:
        """Return the Answer bank record that answers this label, or None."""
        answer_id = self.ids.get(normalize(label))
        return self.records.get(answer_id) if answer_id else None

    def describe(self, label: str, source: str) -> tuple[str, str]:
        """Return (source text, sourceKind) for one filled field."""
        if source == "profile":
            return "Profile", "profile"
        if source == "claude":
            return "Claude, from your profile", "other"
        record = self.record_for(label)
        if record is not None and record["id"].startswith(COMMON_ANSWER_PREFIX):
            return "Common questions", "common_questions"
        if record is not None and record.get("origin") == "reply":
            day = short_date(record.get("updatedAt") or record.get("createdAt"))
            return (f"You answered · {day}" if day else "You answered"), "you"
        return "Answer bank", "answer_bank"

    def filled_field(self, form_field: FormField | None, label: str, value: str, source: str,
                     confidence: int) -> dict:
        """Return the API `FilledField`; a file field shows the file name, not the path."""
        text, kind = self.describe(label, source)
        is_file = form_field is not None and form_field.kind == "file"
        return {
            "label": label,
            "value": Path(value).name if is_file and value else value,
            "source": text,
            "sourceKind": kind,
            "confidence": 100 if source == "profile" else int(confidence),
        }

    def from_answered(self, answered: list[tuple[FormField, FieldAnswer]]) -> list[dict]:
        """Return FilledFields for (FormField, FieldAnswer) pairs, such as the planned fields."""
        return [self.filled_field(form_field, form_field.label, answer.value, answer.source,
                                  answer.confidence)
                for form_field, answer in answered]
