"""The voluntary self-identification answers from setup: gender, Hispanic/Latino, race, veteran
and disability status.

Each is stored in common_answers.json as one of its values below, "decline" ("I don't wish to
answer") or null (not answered yet, so the agent asks the first time a form has it). Race is a
follow-up: setup only asks it when the applicant isn't Hispanic or Latino, like Greenhouse forms.
"""
DECLINE = "decline"

GENDERS = ["Male", "Female", "Non-binary"]
HISPANIC_LATINO = ["Yes", "No"]
RACES = [
    "American Indian or Alaska Native", "Asian", "Black or African American",
    "Native Hawaiian or Other Pacific Islander", "White", "Two or More Races",
]
VETERAN = ["Yes", "No"]
DISABILITY = ["Yes", "No"]

# key -> the values it takes besides "decline"
VALUES = {
    "gender": GENDERS, "hispanicLatino": HISPANIC_LATINO, "race": RACES,
    "veteran": VETERAN, "disability": DISABILITY,
}
KEYS = list(VALUES)
# Setup used to have one "selfId" question: "decline" (always decline) or "ask".
LEGACY_KEY = "selfId"

# How the Answer bank words each answer, when it isn't the value itself
WORDING = {
    DECLINE: "I don’t wish to answer",
    ("veteran", "Yes"): "I identify as a protected veteran",
    ("veteran", "No"): "I am not a protected veteran",
    ("disability", "Yes"): "Yes, I have a disability (or had one in the past)",
    ("disability", "No"): "No, I don’t have a disability",
}


def effective_race(common: dict) -> str | None:
    """The race answer that applies: declining Hispanic/Latino declines race too, and race is
    only asked of applicants who aren't Hispanic or Latino."""
    hispanic = common.get("hispanicLatino")
    if hispanic == DECLINE:
        return DECLINE
    return common.get("race") if hispanic == "No" else None


def answer_wording(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if value == DECLINE:
        return WORDING[DECLINE]
    return WORDING.get((key, value), value)


def migrate_common_answers(doc: dict) -> dict:
    """common_answers.json saved before setup asked each self-ID question.

    `selfId: "decline"` becomes "decline" for every question not already answered, `"ask"`
    leaves them unanswered, and skipping selfId skips them all.
    """
    if LEGACY_KEY not in doc:
        return doc
    migrated = {k: v for k, v in doc.items() if k != LEGACY_KEY}
    if doc[LEGACY_KEY] == DECLINE:
        for key in KEYS:
            migrated.setdefault(key, DECLINE)
    skipped = list(doc.get("skipped") or [])
    if LEGACY_KEY in skipped:
        skipped = [k for k in skipped if k != LEGACY_KEY]
        skipped += [k for k in KEYS if k not in skipped]
    if "skipped" in doc:
        migrated["skipped"] = skipped
    return migrated
