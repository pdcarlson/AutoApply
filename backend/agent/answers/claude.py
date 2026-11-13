"""Asks Claude how to answer a question the profile doesn't cover directly."""
import os
from datetime import date
from functools import cache

import anthropic
from pydantic import BaseModel

from agent.forms.form_field import FieldAnswer
from agent.settings import CLAUDE_MODEL

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
def claude_client():
    """Make the Claude client once and reuse it for every question."""
    return anthropic.Anthropic()


def ask_claude(form_field, facts):
    """Return Claude's answer for one field. Confidence 0 means Claude couldn't help."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return FieldAnswer("", "claude", 0, "No Anthropic API key set.")
    if form_field.options:
        choices = "Answer with exactly one of these choices: " + " | ".join(form_field.options)
    elif form_field.kind == "date":
        # "June 2027" in the facts has to become a day, and "as soon as possible" needs today
        choices = (f"Answer with one date written YYYY-MM-DD. Today is {date.today().isoformat()}"
                   ", so a start date can't be before then.")
    else:
        choices = "Answer in a short line of text."
    prompt = PROMPT.format(facts=facts, label=form_field.label, choices=choices)

    try:
        response = claude_client().messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=ClaudeAnswer,
        )
    except anthropic.APIError as error:
        return FieldAnswer("", "claude", 0, f"Couldn't reach Claude: {error}")

    if response.stop_reason != "end_turn" or response.parsed_output is None:
        return FieldAnswer("", "claude", 0, f"Claude stopped early ({response.stop_reason}).")
    answer = response.parsed_output
    return FieldAnswer(answer.value, "claude", answer.confidence, answer.reason)
