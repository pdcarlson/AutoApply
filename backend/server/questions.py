"""Agent questions: the `AgentQuestion` a job pauses on (spec 2.8).

WP4 builds questions (`make_question`). WP5 adds reading replies (`interpret`), `pick` and
`revise`; accepting lives in server/routes/questions.py (it writes the bank and the queue).

A job in `needs_input` carries the API question in `job.question` and, next to it, the field it
asks about in `job.internal.question` = {fieldKey, label, kind, options}. `options` are exactly
as on the form, so a proposed answer can be checked with the agent's `fits()`.
"""
import re

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


# ----- reading a reply (spec 2.8, a port of mocks/agent.ts interpretReply) -----

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
    """Yes, No, or None when the reply is unsure or unclear (the mock's regexes)."""
    words = " " + text.lower().replace("’", "'") + " "  # curly apostrophes, as in don’t
    if UNSURE.search(words):
        return None
    if NO.search(words):
        return "No"
    if YES.search(words):
        return "Yes"
    return None


def _unique(matches: list[str]) -> str | None:
    return matches[0] if len(matches) == 1 else None


def match_option(text: str, options: list[str]) -> str | None:
    """The one option `text` means, exactly as on the form, or None.

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
    return next((o for o in options if o.strip().casefold() == wanted.casefold()), None)


def interpret(question: dict, internal: dict, text: str) -> dict:
    """Appends the user's reply to `question` and reads it into `proposedAnswer` (in place).

    A field with options only ever gets a value that is exactly one of them, or the agent's
    `fits()` would reject it and the job would ask again forever. When the reply doesn't name
    one, the agent asks again and offers the options to pick from (12 or fewer).
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
            if len(options) <= MAX_PICK_OPTIONS:
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
    if (internal or {}).get("kind") == "text" and value.endswith("."):
        value = value[:-1]
    question["proposedAnswer"] = {"value": value, "confidence": REPLY_CONFIDENCE}
    return question


def pickable(question: dict, internal: dict, value: str) -> bool:
    """True when `value` is one of the question's pickOptions or the field's options."""
    return value in (question.get("pickOptions") or []) \
        or value in ((internal or {}).get("options") or [])


def pick(question: dict, value: str) -> dict:
    question["proposedAnswer"] = {"value": value, "confidence": PICK_CONFIDENCE}
    return question


def revise(question: dict) -> dict:
    question["proposedAnswer"] = None
    return question
