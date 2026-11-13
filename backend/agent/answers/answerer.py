"""Decides what the agent puts in each form field."""
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


class Answerer:
    """Answers a field from the profile, then saved answers, then Claude."""

    def __init__(self, profile, ask_claude, threshold=CONFIDENCE_THRESHOLD):
        self.profile = profile
        self.ask_claude = ask_claude
        self.threshold = threshold
        # The form runs again after the applicant answers questions, so Claude isn't asked twice
        self.claude_answers = {}

    def answer(self, form_field):
        """Return a FieldAnswer, or None if the agent should ask the applicant instead."""
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
        key = form_field.profile_key
        if not key and len(form_field.label.split()) <= MAX_LABEL_WORDS:
            label = form_field.label.lower()
            key = next((attr for word, attr in LABEL_WORDS.items() if word in label), "")
        return getattr(self.profile, key, "") if key else ""


def fits(form_field, value):
    """Return True if the value is allowed in this field (one of the options, for dropdowns)."""
    return not form_field.options or value in form_field.options
