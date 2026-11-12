"""Agent questions: the `AgentQuestion` a job pauses on (spec 2.8).

WP4 builds questions (`make_question`); WP5 adds reply interpretation, pick, revise and accept.

A job in `needs_input` carries the API question in `job.question` and, next to it, the field it
asks about in `job.internal.question` = {fieldKey, label, kind, options}. `options` are exactly
as on the form, so a proposed answer can be checked with the agent's `fits()`.
"""
from agent.forms.form_field import FieldAnswer, FormField

NOTHING_FOUND = "Nothing in your profile or Answer bank answers this."
MAX_PICK_OPTIONS = 12
LISTED_OPTIONS = 5


def question_id(job_id: str, n: int) -> str:
    return f"q-{job_id}-{n}"


def is_yes_no(options: list[str]) -> bool:
    return len(options) == 2 and {o.strip().lower() for o in options} == {"yes", "no"}


def _first_message(form_field: FormField, guess: FieldAnswer | None) -> str:
    options = form_field.options
    if options and is_yes_no(options):
        return f"{NOTHING_FOUND} Pick one, or reply in your own words."
    if options and len(options) <= MAX_PICK_OPTIONS:
        listed = ", ".join(options[:LISTED_OPTIONS])
        more = len(options) - LISTED_OPTIONS
        if more > 0:
            listed += f" and {more} more"
        return f"{NOTHING_FOUND} Pick one ({listed}), or reply in your own words."
    if options:
        return "Reply with the option you want; it has to match one on the form."
    if guess is not None and guess.value:
        return (f"My best guess is “{guess.value}”, but I’m only {guess.confidence}% sure. "
                "Reply “yes” to use it, or tell me the right answer.")
    return f"{NOTHING_FOUND} What should I enter?"


def make_question(job_id: str, n: int, form_field: FormField,
                  guess: FieldAnswer | None = None) -> tuple[dict, dict]:
    """(API AgentQuestion, internal field record) for the `n`th question a job asks.

    `guess` is Claude's below-threshold answer for the field, if it had one
    (`answerer.claude_answers[field.key]`); only text and textarea questions quote it.
    """
    options = list(form_field.options)
    yes_no = bool(options) and is_yes_no(options)
    if yes_no:
        placeholder = "e.g. Yes"
    elif form_field.kind == "textarea":
        placeholder = "A sentence or two in your own words"
    else:
        placeholder = "e.g. the right answer"
    usable_guess = guess if guess is not None and guess.value and not options else None
    question = {
        "id": question_id(job_id, n),
        "type": "yesno" if yes_no else "confirm",
        "field": form_field.label,
        "confidence": int(guess.confidence) if guess is not None and guess.value else 0,
        "draft": None,
        "messages": [{"from": "agent", "text": _first_message(form_field, usable_guess)}],
        "placeholder": placeholder,
        "pickOptions": options if options and len(options) <= MAX_PICK_OPTIONS else None,
        "proposedAnswer": None,
        "defaultScope": "company" if form_field.kind == "textarea" else "all",
    }
    internal = {"fieldKey": form_field.key, "label": form_field.label, "kind": form_field.kind,
                "options": options}
    return question, internal
