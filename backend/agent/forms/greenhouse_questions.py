"""Turns Greenhouse's Job Board API question list into FormFields."""
import re

from agent.forms.form_field import FieldKind, FormField
from agent.forms.greenhouse_education import education_fields

KINDS = {
    "input_text": FieldKind.TEXT,
    "textarea": FieldKind.TEXTAREA,
    "input_file": FieldKind.FILE,
    "multi_value_single_select": FieldKind.SELECT,
    "multi_value_multi_select": FieldKind.MULTI_SELECT,
}
PROFILE_FIELDS = {
    "first_name": "first_name",
    "last_name": "last_name",
    "preferred_name": "preferred_name",
    "email": "email",
    "phone": "phone",
    "resume": "resume_path",
}
# Compliance box id -> the profile's self-ID answer for it
SELF_ID_FIELDS = {
    "gender": "gender",
    "hispanic_ethnicity": "hispanic_latino",
    "race": "race",
    "veteran_status": "veteran",
    "disability_status": "disability",
}
# The Hispanic/Latino box the page shows above race, which the API leaves out
HISPANIC = ("hispanic_ethnicity", "Are you Hispanic/Latino?",
            ["Yes", "No", "Decline To Self Identify"])
# The API writes some labels run together, like "VeteranStatus"
RUN_TOGETHER = re.compile(r"(?<=[a-z])(?=[A-Z])")


def fields_from_api(job: dict, education_options: dict | None = None,
                    education_config: dict | None = None) -> list[FormField]:
    """Turn the Job Board API's question list into FormFields.

    education_options has the Education section's {"degrees": [...], "disciplines": [...]}.
    education_config is the page's {"start_year": "required", ...}, or None if unknown.
    """
    fields = main_fields(job)
    # The city box is listed separately, and on the page its id is candidate-location
    for question in job.get("location_questions", []):
        if any(item["name"] == "location" for item in question.get("fields", [])):
            fields.append(FormField("candidate-location", question["label"], FieldKind.LOCATION,
                                    question.get("required", False), profile_key="location"))
    # The phone box comes with a required country dropdown that the API doesn't list
    if any(form_field.key == "phone" for form_field in fields):
        fields.append(FormField("country", "Country", FieldKind.SELECT, True,
                                profile_key="country"))
    return (fields + education_fields(job, education_options or {}, education_config)
            + demographic_fields(job) + compliance_fields(job))


def main_fields(job: dict) -> list[FormField]:
    """Return the questions in the API's main question list."""
    fields = []
    for question in job.get("questions", []):
        items = question.get("fields", [])
        has_file = any(item["type"] == "input_file" for item in items)
        for item in items:
            # File questions also offer a "type it in instead" box, and the file is enough
            if has_file and item["type"] != "input_file":
                continue
            kind = KINDS.get(item["type"])
            if kind is None:
                continue
            fields.append(FormField(
                key=item["name"],
                label=question["label"].strip(),
                kind=kind,
                required=question.get("required", False),
                options=[value["label"].strip() for value in item.get("values", [])],
                profile_key=PROFILE_FIELDS.get(item["name"], ""),
            ))
    return fields


def demographic_fields(job: dict) -> list[FormField]:
    """Return the questions in the API's demographic_questions section.

    Despite the name, forms use this section for questions like "Are you legally authorized
    to work in the United States?", and they can be required. Each has an id (the page's box
    has that id) instead of a field name, and answer_options instead of values.
    """
    fields = []
    for question in (job.get("demographic_questions") or {}).get("questions", []):
        kind = KINDS.get(question.get("type", ""))
        if kind is None:
            continue
        fields.append(FormField(
            key=str(question["id"]),
            label=question["label"].strip(),
            kind=kind,
            required=question.get("required", False),
            # Labels can have stray spaces, like "No " on SingleStore's sponsorship question
            options=[option["label"].strip() for option in question.get("answer_options", [])],
        ))
    return fields


def compliance_fields(job: dict) -> list[FormField]:
    """Return the EEOC questions (gender, race, veteran status, disability), by their box ids.

    The page asks "Are you Hispanic/Latino?" before race and only shows race after "No". The
    API doesn't list that box, so it's added in front of race.
    """
    fields = []
    for section in job.get("compliance") or []:
        for question in section.get("questions", []):
            for item in question.get("fields", []):
                kind = KINDS.get(item["type"])
                if kind is None:
                    continue
                if item["name"] == "race":
                    key, label, options = HISPANIC
                    fields.append(FormField(key, label, FieldKind.SELECT, options=list(options),
                                            profile_key=SELF_ID_FIELDS[key]))
                fields.append(FormField(
                    key=item["name"],
                    label=RUN_TOGETHER.sub(" ", question["label"].strip()),
                    kind=kind,
                    required=question.get("required", False),
                    options=[value["label"].strip() for value in item.get("values", [])],
                    profile_key=SELF_ID_FIELDS.get(item["name"], ""),
                ))
    return fields


def compliance_keys(job: dict) -> set[str]:
    """Return the ids of the compliance boxes, some of which a page only shows after others."""
    return {form_field.key for form_field in compliance_fields(job)}
