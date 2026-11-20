"""How a run ended, and the reasons it gives the applicant."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.runner.held_form import HeldForm

CANCELLED = "Cancelled."
CONFIRMED = "The site confirmed the application."
NOT_CONFIRMED = "Pressed Submit but never saw a confirmation."
ASKED_FOR_CODE = "The site asked for the verification code it emailed."
CODE_REJECTED = ("The site didn't take that code. Check that it's from the newest email the "
                 "site sent, and try again.")
NO_CODE_PROMPT = "The form window isn't asking for a code anymore, so nothing was typed."
WINDOW_CLOSED = "The form window was closed before the application was confirmed."
FORM_GONE = ("The form window doesn't show the form anymore, so the agent didn't press Submit. "
             "Finish it in that window, or close the window to have the form filled again.")


class RunStatus(StrEnum):
    """How a run ended."""

    PENDING = ""  # still running: the status isn't known yet
    NEEDS_INPUT = "needs_input"
    READY = "ready"
    HANDOFF = "handoff"
    SUBMITTED = "submitted"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunResult:  # pylint: disable=too-many-instance-attributes  # one flat record the server reads
    """How a run ended, and what it filled along the way."""

    status: RunStatus
    reason: str = ""
    questions: list = field(default_factory=list)  # FormFields the applicant has to answer
    filled: list = field(default_factory=list)  # (label, value, source) for each filled field
    screenshot: str = ""  # the last screenshot taken
    # (FormField, FieldAnswer) for every field the agent has an answer for, set on every return
    answered: list = field(default_factory=list)
    filled_detail: list = field(default_factory=list)  # (label, value, source, confidence)
    filled_screenshot: str = ""  # taken after the last field is filled, before Submit
    held: HeldForm | None = None  # the still-open form, for `ready` or `handoff` with hold=True
    asked_for_code: bool = False  # no confirmation, and the site is asking for an emailed code
    pressed: bool = False  # Submit was pressed (so the application may have gone out)
    window_closed: bool = False  # the page or browser went away (closed by the person)
    # Handoffs for the steps the agent left alone (CAPTCHA, sign-in, password, SSN)
    protected: list = field(default_factory=list)

    def __post_init__(self):
        """Accept the status as plain text too, as callers outside the agent pass it."""
        self.status = RunStatus(self.status)

    def end(self, status: RunStatus, reason: str) -> None:
        """Set how the run ended."""
        self.status, self.reason = status, reason

    def copy_filled(self) -> RunResult:
        """Return a new pending result that carries over what this one filled."""
        return RunResult(RunStatus.PENDING, filled=list(self.filled),
                         filled_detail=list(self.filled_detail),
                         screenshot=self.filled_screenshot,
                         filled_screenshot=self.filled_screenshot)
