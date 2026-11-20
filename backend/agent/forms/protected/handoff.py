"""A step on a form the applicant has to do themselves, and why."""
from dataclasses import dataclass
from enum import StrEnum


class HandoffKind(StrEnum):
    """The kinds of step the agent never does itself."""

    CAPTCHA = "captcha"
    SSN = "ssn"
    PASSWORD = "password"
    LOGIN = "login"


@dataclass(frozen=True)
class Handoff:
    """One step the applicant has to do themselves, and why."""

    kind: HandoffKind
    label: str
    message: str


def merge(handoffs: list[Handoff], found: list[Handoff]) -> list[Handoff]:
    """Add the newly found Handoffs to the list, skipping ones already there."""
    for handoff in found:
        if handoff not in handoffs:
            handoffs.append(handoff)
    return handoffs


def handoff_reason(handoffs: list[Handoff]) -> str:
    """Return one plain reason for the applicant, with one sentence per kind of step."""
    seen = []
    for handoff in handoffs:
        if handoff.message not in seen:
            seen.append(handoff.message)
    return " ".join(seen)
