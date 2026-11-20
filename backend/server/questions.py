"""The question a job pauses on when the agent can't answer a form field, and reading replies."""
# A job in `needs_input` carries the API question in `job.question` and, next to it, the field it
# asks about in `job.internal.question` = {fieldKey, label, kind, options}. `options` are exactly
# as on the form, so a proposed answer can be checked with the agent's `fits()`.
import re

from agent.forms.dates import iso_date
from agent.forms.form_field import FieldAnswer, FormField

NOTHING_FOUND = "Nothing in your profile or Answer bank answers this."
DATE_EXAMPLE = "June 1, 2027"


def question_id(job_id: str, number: int) -> str:
    """Return the id of the `number`th question a job asks."""
    return f"q-{job_id}-{number}"


def is_yes_no(options: list[str]) -> bool:
    """Return True when the options are exactly Yes and No."""
    return len(options) == 2 and {o.strip().lower() for o in options} == {"yes", "no"}


def _first_message(form_field: FormField, guess: FieldAnswer | None) -> str:
    """Return the agent's opening message for the question."""
    if form_field.options:
        # The frontend shows the options to pick from and no reply box
        return f"{NOTHING_FOUND} Pick one."
    if guess is not None and guess.value:
        return (f"My best guess is “{guess.value}”, but I’m only {guess.confidence}% sure. "
                "Reply “yes” to use it, or tell me the right answer.")
    return f"{NOTHING_FOUND} What should I enter?"


def _placeholder(form_field: FormField, yes_no: bool) -> str:
    """Return the reply box's placeholder for the field."""
    if yes_no:
        return "e.g. Yes"
    if form_field.kind == "textarea":
        return "A sentence or two in your own words"
    if form_field.kind == "date":
        return f"e.g. {DATE_EXAMPLE}"
    return "e.g. the right answer"


def make_question(job_id: str, number: int, form_field: FormField,
                  guess: FieldAnswer | None = None) -> tuple[dict, dict]:
    """Return (API AgentQuestion, internal field record) for the `number`th question a job asks.

    `guess` is Claude's below-threshold answer for the field, if it had one; only text and
    textarea questions quote it.
    """
    options = list(form_field.options)
    yes_no = bool(options) and is_yes_no(options)
    placeholder = _placeholder(form_field, yes_no)
    usable_guess = guess if guess is not None and guess.value and not options else None
    question = {
        "id": question_id(job_id, number),
        "type": "yesno" if yes_no else "confirm",
        "field": form_field.label,
        "confidence": int(guess.confidence) if guess is not None and guess.value else 0,
        "draft": None,
        "messages": [{"from": "agent", "text": _first_message(form_field, usable_guess)}],
        "placeholder": placeholder,
        # Every option, however many: a field with options is answered by picking one
        "pickOptions": options or None,
        "proposedAnswer": None,
        "defaultScope": "company" if form_field.kind == "textarea" else "all",
    }
    internal = {"fieldKey": form_field.key, "label": form_field.label, "kind": form_field.kind,
                "options": options}
    return question, internal


# ----- reading a reply (the same rules as the frontend's mock agent) -----

UNSURE = re.compile(r"\b(maybe|depends|not sure|unsure|idk|possibly|might|perhaps|probably)\b")
NO = re.compile(r"\b(no|nope|nah|not|never|can't|cannot|won't|wouldn't|don't)\b")
YES = re.compile(r"\b(yes|yeah|yep|sure|ok|okay|definitely|absolutely|happy|willing|fine|i can"
                 r"|i would|i'd|i will|of course)\b")
AGREE = re.compile(r"^\s*(yes|yeah|yep|correct|right|looks good|sure|ok|okay)\b", re.IGNORECASE)
QUOTED_GUESS = re.compile(r"“(.+?)”")

OPTION_CONFIDENCE = 96
GUESS_CONFIDENCE = 97
REPLY_CONFIDENCE = 95
PICK_CONFIDENCE = 100


def _yes_no_value(text: str) -> str | None:
    """Return Yes, No, or None when the reply is unsure or unclear."""
    words = " " + text.lower().replace("’", "'") + " "  # curly apostrophes, as in don’t
    if UNSURE.search(words):
        return None
    if NO.search(words):
        return "No"
    if YES.search(words):
        return "Yes"
    return None


def _unique(matches: list[str]) -> str | None:
    """Return the only match, or None when there are none or several."""
    return matches[0] if len(matches) == 1 else None


def match_option(text: str, options: list[str]) -> str | None:
    """Return the one option `text` means, exactly as on the form, or None.

    In order: a case-insensitive exact match, then the only option contained in the reply as
    whole words (so "He" isn't found in "she"), then the only option that starts with the reply.
    """
    reply = text.strip().casefold()
    if not reply:
        return None
    exact = _unique([o for o in options if o.strip().casefold() == reply])
    if exact is not None:
        return exact
    contained = _unique([o for o in options if o.strip() and re.search(
        rf"(?<!\w){re.escape(o.strip().casefold())}(?!\w)", reply)])
    if contained is not None:
        return contained
    return _unique([o for o in options if o.strip().casefold().startswith(reply)])


def _option_for(options: list[str], wanted: str) -> str | None:
    """Return the option that is `wanted` ignoring case, or None."""
    return next((o for o in options if o.strip().casefold() == wanted.casefold()), None)


def interpret(question: dict, internal: dict, text: str) -> dict:
    """Append the user's reply to `question` and read it into `proposedAnswer`; return it.

    A field with options only ever gets a value that is exactly one of them, or the agent's
    `fits()` would reject it and the job would ask again forever. When the reply doesn't name
    one, the agent asks again and offers the options to pick from.
    """
    question["messages"].append({"from": "you", "text": text})
    options = list((internal or {}).get("options") or [])
    if options:
        if is_yes_no(options):
            said = _yes_no_value(text)
            value = _option_for(options, said) if said else None
        else:
            value = match_option(text, options)
        if value is None:
            question["messages"].append({
                "from": "agent",
                "text": f"This field only takes one of: {', '.join(options)}. Which one fits?"})
            question["pickOptions"] = options
            return question
        question["proposedAnswer"] = {"value": value, "confidence": OPTION_CONFIDENCE}
        return question

    first = question["messages"][0]["text"] if question["messages"] else ""
    guess = QUOTED_GUESS.search(first) if first else None
    if AGREE.search(text) and guess:
        question["proposedAnswer"] = {"value": guess.group(1), "confidence": GUESS_CONFIDENCE}
        return question
    value = text.strip()
    if (internal or {}).get("kind") == "date":
        # Kept as YYYY-MM-DD, or the agent's `fits()` would reject it and ask again forever
        value = iso_date(value)
        if not value:
            question["messages"].append({
                "from": "agent",
                "text": f"This field takes a date, like {DATE_EXAMPLE}. What date should I put?"})
            return question
    elif (internal or {}).get("kind") == "text" and value.endswith("."):
        value = value[:-1]
    question["proposedAnswer"] = {"value": value, "confidence": REPLY_CONFIDENCE}
    return question


def pickable(question: dict, internal: dict, value: str) -> bool:
    """Return True when `value` is one of the question's pickOptions or the field's options."""
    return value in (question.get("pickOptions") or []) \
        or value in ((internal or {}).get("options") or [])


def pick(question: dict, value: str) -> dict:
    """Propose the option the user picked and return the question."""
    question["proposedAnswer"] = {"value": value, "confidence": PICK_CONFIDENCE}
    return question


def revise(question: dict) -> dict:
    """Clear the proposed answer so the user can give another, and return the question."""
    question["proposedAnswer"] = None
    return question
