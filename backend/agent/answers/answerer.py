"""Decides what the agent puts in each form field."""
import re
from dataclasses import replace

from agent.answers import self_id
from agent.forms.dates import iso_date
from agent.forms.form_field import FieldAnswer
from agent.settings import CONFIDENCE_THRESHOLD

# Link questions are worded differently on every form, so they're matched by a word in
# the label. Only short labels count, so a long question that mentions LinkedIn isn't
# answered with a URL. A "Middle Name" box (a custom question on some forms) is matched too.
LABEL_WORDS = {
    "middle name": "middle_name",
    "linkedin": "linkedin",
    "github": "github",
    "website": "website",
    "portfolio": "website",
}
MAX_LABEL_WORDS = 4
# How a degree's level starts on degree dropdowns, for the ways resumes write degrees.
# The MBA comes before other master's degrees so it isn't read as "Master's".
DEGREE_LEVELS = [
    (r"\bm\.?b\.?a(?![a-z])|business administration", "Master of Business Administration"),
    (r"\bmaster|\bm\.?(s|a|sc|eng|tech)\.?(?![a-z])", "Master's"),
    (r"\bbachelor|\bb\.?(s|a|sc|eng|tech)\.?(?![a-z])", "Bachelor's"),
    (r"\bph\.?d|doctor of philosophy|doctorate", "Doctor of Philosophy"),
    (r"\bassociate", "Associate's"),
]


class Answerer:
    """Answers a field from the profile, then saved answers, then Claude."""

    def __init__(self, profile, ask_claude, threshold=CONFIDENCE_THRESHOLD):
        self.profile = profile
        self.ask_claude = ask_claude
        self.threshold = threshold
        # The form runs again after the applicant answers questions, so Claude isn't asked twice
        self.claude_answers = {}

    def answer(self, form_field):
        """Return a FieldAnswer, or None if the agent should ask the applicant instead.

        Dates come back as YYYY-MM-DD however they were written ("June 2027", "ASAP").
        """
        found = self.first_answer(form_field)
        if found is not None and form_field.kind == "date":
            value = iso_date(found.value)
            found = replace(found, value=value) if value else None
        return found

    def first_answer(self, form_field):
        """The answer from the first source that has one that fits, or None."""
        value = self.from_profile(form_field)
        if value:
            return FieldAnswer(value, "profile")

        saved = self.profile.saved_answer(form_field.label)
        if saved is not None and fits(form_field, saved):
            return FieldAnswer(saved, "saved")

        # Claude can't attach files, and it shouldn't guess at anything it isn't sure of
        if form_field.kind == "file":
            return None
        if form_field.key not in self.claude_answers:
            self.claude_answers[form_field.key] = self.ask_claude(form_field, self.profile.facts())
        guess = self.claude_answers[form_field.key]
        if guess.value and guess.confidence >= self.threshold and fits(form_field, guess.value):
            return guess
        return None

    def from_profile(self, form_field):
        """Return the profile value for a standard field like email, or an empty string."""
        if self_id.self_id_key(form_field):
            return self_id.choose(form_field, self.profile)
        key = form_field.profile_key
        if not key and len(form_field.label.split()) <= MAX_LABEL_WORDS:
            label = form_field.label.lower()
            key = next((attr for word, attr in LABEL_WORDS.items() if word in label), "")
        value = getattr(self.profile, key, "") if key else ""
        if value and form_field.options:
            # A dropdown takes only its own wording, so "Bachelor's" becomes "Bachelor's Degree".
            # With no clear match, saved answers or Claude pick the option instead.
            option = closest_option(form_field.options, value)
            if not option and key == "degree":
                option = closest_option(form_field.options, degree_level(value))
            return option
        return value


def degree_level(degree):
    """Return how dropdowns name a degree's level ("M.S." -> "Master's"), or ""."""
    return next((level for pattern, level in DEGREE_LEVELS
                 if re.search(pattern, degree, re.IGNORECASE)), "")


def closest_option(options, value):
    """Return the option that is the value (any case), or the only one starting with it, or ""."""
    wanted = " ".join(value.lower().split())
    exact = [option for option in options if " ".join(option.lower().split()) == wanted]
    if exact:
        return exact[0]
    starts = [option for option in options if option.lower().startswith(wanted)]
    return starts[0] if len(starts) == 1 else ""


def fits(form_field, value):
    """Return True if the value is allowed in this field: one of the options for dropdowns, and
    something that reads as a date for date questions."""
    if form_field.kind == "date":
        return bool(iso_date(value))
    return not form_field.options or value in form_field.options
