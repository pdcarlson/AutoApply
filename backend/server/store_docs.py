"""The JSON documents a Store keeps, their default values, and upgrades for older versions."""
from typing import Any, Callable

from server.names import migrate_profile, split_name
from server.self_id import migrate_common_answers

SCHEMA = 1
DEMO_USER = {"id": "local", "name": "Demo User", "email": "demo@example.com"}


def default_state() -> dict:
    """Return state.json for a new user: signed out, nothing confirmed, an empty queue."""
    return {"schema": SCHEMA, "signedIn": False, "profileConfirmed": False, "paused": False,
            "queue": []}


def default_profile() -> dict:
    """Return the empty profile the frontend's mock starts with, under the demo user's name."""
    first, middle, last = split_name(DEMO_USER["name"])
    return {
        "firstName": first, "middleName": middle, "lastName": last,
        "email": DEMO_USER["email"],
        "phone": "", "street": "", "street2": "", "city": "", "state": "", "zip": "",
        "country": "United States",
        "links": [
            {"id": "web", "label": "Website / portfolio", "url": "", "fixed": True},
            {"id": "linkedin", "label": "LinkedIn", "url": "", "fixed": True},
            {"id": "github", "label": "GitHub", "url": "", "fixed": True},
        ],
        "education": [], "experience": [], "projects": [], "skills": [], "custom": [],
        "resume": None,
        "unplaced": [],
    }


def default_common_answers() -> dict:
    """Return common_answers.json with nothing answered yet."""
    return {
        "workAuthorized": None, "needsSponsorship": None, "graduation": None, "earliestStart": None,
        "relocate": None, "locations": ["Remote (US)"], "expectedPay": "", "familyEmployers": [],
        "gender": None, "hispanicLatino": None, "race": None, "veteran": None, "disability": None,
        "skipped": [],
    }


def default_preferences() -> dict:
    """Return the job preferences a new user starts with."""
    return {"roleTypes": [], "fullTime": True, "internship": False}


def default_settings() -> dict:
    """Return the agent settings a new user starts with."""
    return {"confidenceThreshold": 90, "dailyLimit": 25}


def migrate_applications(records: list) -> list:
    """Upgrade applications.json saved while `screenshotUrl` showed the filled form.

    The thank-you page was then the server-only `_resultScreenshot`; it is shown instead now.
    """
    migrated = []
    for record in records:
        if isinstance(record, dict) and "_resultScreenshot" in record:
            record = dict(record)
            name = record.pop("_resultScreenshot")
            if name:
                record["screenshotUrl"] = f"/api/screenshots/{name}"
        migrated.append(record)
    return migrated


# Doc name -> factory for its default value. The file is `<name>.json`. Add docs here.
DOC_DEFAULTS: dict[str, Callable[[], Any]] = {
    "state": default_state,
    "profile": default_profile,
    "resume_parse": lambda: None,
    "common_answers": default_common_answers,
    "preferences": default_preferences,
    "settings": default_settings,
    "jobs": list,
    "applications": list,
}

# Doc name -> function that upgrades a doc saved by an older version, applied on load before
# missing keys get their defaults. The upgraded doc is written back on its next change.
DOC_MIGRATIONS: dict[str, Callable[[Any], Any]] = {
    "profile": migrate_profile,
    "common_answers": migrate_common_answers,
    "applications": migrate_applications,
}
