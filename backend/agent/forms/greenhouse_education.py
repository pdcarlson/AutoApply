"""The boxes in a Greenhouse form's Education section, which its API doesn't list."""
import json
import re
from calendar import month_name
from dataclasses import dataclass

from agent.forms.form_field import FieldKind, FormField

MONTHS = list(month_name)[1:]
# Where the form's page keeps its education_config, which has no nested braces
EDUCATION_CONFIG = re.compile(r'"education_config"\s*:\s*(\{[^{}]*\})')
# The API's "education" setting for a form that has an Education section
HAS_EDUCATION = ("education_optional", "education_required")


@dataclass(frozen=True)
class EducationBox:
    """One box the Education section can show."""

    key: str  # the box's id on the page
    label: str
    kind: FieldKind
    profile_key: str
    config_name: str  # its name in the page's education_config
    # Whether it's required on an education_required form with no education_config, as real
    # forms were seen requiring (Duolingo requires all five)
    usually_required: bool


# The API only says whether the form has an Education section, not which of these boxes it
# shows or requires. The page's education_config says that, so it's used when it can be read;
# without it, every box is read and the ones a form leaves out are skipped while filling.
EDUCATION_BOXES = [
    EducationBox("school--0", "School", FieldKind.SCHOOL, "school", "school_name", True),
    EducationBox("degree--0", "Degree", FieldKind.SELECT, "degree", "degree", True),
    EducationBox("discipline--0", "Discipline", FieldKind.SELECT, "major", "discipline", True),
    EducationBox("start-month--0", "Education start date month", FieldKind.SELECT,
                 "school_start_month", "start_month", False),
    EducationBox("start-year--0", "Education start date year", FieldKind.TEXT,
                 "school_start_year", "start_year", False),
    EducationBox("end-month--0", "Education end date month", FieldKind.SELECT,
                 "graduation_month", "end_month", True),
    EducationBox("end-year--0", "Education end date year", FieldKind.TEXT,
                 "graduation_year", "end_year", True),
]
EDUCATION_KEYS = {box.key for box in EDUCATION_BOXES}


def education_fields(job: dict, options: dict, config: dict | None = None) -> list[FormField]:
    """Return the Education section's boxes, or nothing if the form doesn't have one.

    `options` holds the API's {"degrees": [...], "disciplines": [...]}. With the page's
    education_config, only the boxes it shows are returned, and the ones it marks "required"
    are required. Without it, the usual boxes are guessed at.
    """
    setting = job.get("education", "")
    if setting not in HAS_EDUCATION:
        return []
    choices = {"degree--0": options.get("degrees", []),
               "discipline--0": options.get("disciplines", []),
               "start-month--0": MONTHS, "end-month--0": MONTHS}
    fields = []
    for box in EDUCATION_BOXES:
        if config:
            if config.get(box.config_name) not in ("required", "optional"):
                continue
            required = config[box.config_name] == "required"
        else:
            required = box.usually_required and setting == "education_required"
        fields.append(FormField(box.key, box.label, box.kind, required,
                                options=list(choices.get(box.key, [])),
                                profile_key=box.profile_key))
    return fields


def education_config_from_page(html: str) -> dict | None:
    """Return the page's {"start_year": "required", "discipline": "hidden", ...}, or None."""
    match = EDUCATION_CONFIG.search(html)
    if not match:
        return None
    try:
        config = json.loads(match.group(1))
    except ValueError:
        return None
    return config if isinstance(config, dict) else None
