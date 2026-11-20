"""Asks Claude how to answer a question the profile doesn't cover directly."""
from datetime import date
from functools import cache

import anthropic
from pydantic import BaseModel

from agent.forms.form_field import AnswerSource, FieldAnswer, FieldKind, FormField
from agent.settings import CLAUDE_MODEL, has_anthropic_key

MAX_TOKENS = 4000
PROMPT = """You are filling out a job application for the applicant below.

Applicant facts:
{facts}

Form question: {label}
{choices}

Answer using only the applicant facts. Read the question carefully, since some are worded
backwards (for example "Can you work here without sponsorship?").
If the facts don't clearly answer the question, give a confidence under 50 and leave value empty.
For gender, race, veteran and disability questions, pick the option that declines to answer
when the facts say to decline.
Confidence is 0 to 100."""


class ClaudeAnswer(BaseModel):
    """The shape Claude has to reply in."""

    value: str
    confidence: int
    reason: str


@cache
def claude_client() -> anthropic.Anthropic:
    """Make the Claude client once and reuse it for every question."""
    return anthropic.Anthropic()


def _no_answer(reason: str) -> FieldAnswer:
    """Return the empty answer that means Claude couldn't help."""
    return FieldAnswer("", AnswerSource.CLAUDE, 0, reason)


def _choices(form_field: FormField) -> str:
    """Return the line that tells Claude what shape of answer the field takes."""
    if form_field.options:
        return "Answer with exactly one of these choices: " + " | ".join(form_field.options)
    if form_field.kind is FieldKind.DATE:
        # "June 2027" in the facts has to become a day, and "as soon as possible" needs today
        return (f"Answer with one date written YYYY-MM-DD. Today is {date.today().isoformat()}"
                ", so a start date can't be before then.")
    return "Answer in a short line of text."


def ask_claude(form_field: FormField, facts: str) -> FieldAnswer:
    """Return Claude's answer for one field. Confidence 0 means Claude couldn't help."""
    if not has_anthropic_key():
        return _no_answer("No Anthropic API key set.")
    prompt = PROMPT.format(facts=facts, label=form_field.label, choices=_choices(form_field))
    try:
        response = claude_client().messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=ClaudeAnswer,
        )
    except anthropic.APIError as error:
        return _no_answer(f"Couldn't reach Claude: {error}")

    if response.stop_reason != "end_turn" or response.parsed_output is None:
        return _no_answer(f"Claude stopped early ({response.stop_reason}).")
    answer = response.parsed_output
    return FieldAnswer(answer.value, AnswerSource.CLAUDE, answer.confidence, answer.reason)
