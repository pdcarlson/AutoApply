"""Picks the option for voluntary self-identification questions from the applicant's answers."""
import re

from agent.forms.form_field import FormField

DECLINE = "decline"
HISPANIC = "Hispanic"
# Profile attributes, which are also the profile_key of self-ID fields
KEYS = ("gender", "hispanic_latino", "race", "veteran", "disability")
MAX_LABEL_WORDS = 4

# Forms word these choices differently ("Decline To Self Identify", "I don't wish to answer",
# "I am not a protected veteran"), so each answer is matched to an option by its meaning
# rather than its exact wording. With no clear match the field is left for saved answers or
# Claude.
DECLINES = re.compile(
    r"decline|don.?t (wish|want)|do not (wish|want)|prefer not|rather not|not (to )?(answer|"
    r"disclose|say|specify|self.?identify)|choose not", re.IGNORECASE)
# A short label that asks one of these questions, for forms that don't mark them
LABELS = [
    (re.compile(r"\bgender\b", re.IGNORECASE), "gender"),
    (re.compile(r"\bhispanic|\blatin[oax]", re.IGNORECASE), "hispanic_latino"),
    (re.compile(r"\brace\b", re.IGNORECASE), "race"),
    (re.compile(r"\bveteran", re.IGNORECASE), "veteran"),
    (re.compile(r"\bdisabilit", re.IGNORECASE), "disability"),
]
# How options say each answer, for answers whose wording varies by form
MEANINGS = {
    ("veteran", "Yes"): r"^(yes|i am a protected|i identify as (one or more|a protected))",
    ("veteran", "No"): r"^(no\b|i am not a( protected)? veteran|not a protected)",
    ("disability", "Yes"): r"^yes",
    ("disability", "No"): r"^no\b",
    ("hispanic_latino", "Yes"): r"^yes",
    ("hispanic_latino", "No"): r"^no\b",
    ("gender", "Male"): r"^(male|man)\b",
    ("gender", "Female"): r"^(female|woman)\b",
    ("gender", "Non-binary"): r"^non.?binary",
    ("race", "American Indian or Alaska Native"): r"american indian|alaskan? native",
    ("race", "Black or African American"): r"\bblack\b|african american",
    ("race", "Native Hawaiian or Other Pacific Islander"): r"hawaiian|pacific islander",
    ("race", "Two or More Races"): r"two or more|multi.?racial",
    ("race", "Asian"): r"^asian\b",
    ("race", "White"): r"^white\b",
}
HISPANIC_RACE = re.compile(r"hispanic|latin[oax]", re.IGNORECASE)


def self_id_key(form_field: FormField) -> str:
    """Return the profile attribute a field asks about ("gender", "race", ...), or ""."""
    if form_field.profile_key in KEYS:
        return form_field.profile_key
    if not form_field.options or len(form_field.label.split()) > MAX_LABEL_WORDS:
        return ""
    return next((key for pattern, key in LABELS if pattern.search(form_field.label)), "")


def choose(form_field: FormField, profile) -> str:
    """Return the option matching the applicant's self-ID answer, or "" to leave it to others."""
    key = self_id_key(form_field)
    if not key or not form_field.options:
        return ""
    answer = _profile_answer(key, profile)
    if not answer:
        return ""
    pattern = _meaning(key, answer)
    matches = [option for option in form_field.options if pattern.search(option.strip())]
    return matches[0] if len(matches) == 1 else ""


def _profile_answer(key: str, profile) -> str:
    """Return the applicant's answer to one self-ID question, DECLINE, HISPANIC or ""."""
    answer = getattr(profile, key, "") or (DECLINE if profile.eeo == DECLINE else "")
    if key == "race" and not answer and profile.hispanic_latino == DECLINE:
        answer = DECLINE
    if key == "race" and not answer and profile.hispanic_latino == "Yes":
        # Forms that ask race in one list include "Hispanic or Latino" in it
        answer = HISPANIC
    return answer


def _meaning(key: str, answer: str) -> re.Pattern:
    """Return the pattern an option has to match to mean this answer."""
    if answer == DECLINE:
        return DECLINES
    if answer == HISPANIC:
        return HISPANIC_RACE
    return re.compile(MEANINGS.get((key, answer), re.escape(answer)), re.IGNORECASE)
