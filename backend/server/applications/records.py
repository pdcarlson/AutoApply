"""Application records in applications.json: their API shape, and how a job becomes one."""
import secrets
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from agent.runner.apply_run import RunResult
from server import jobs
from server.errors import ApiError
from server.jobs import EventKind, JobState
from server.routes.files import screenshot_url
from server.store import Db, Store, parse_iso

# Keys of the API `Application`, in types.ts order. ApplicationDetail adds DETAIL_KEYS.
SUMMARY_KEYS = ("id", "jobId", "company", "role", "location", "ats", "url", "status",
                "submittedAt", "submittedBy", "confirmation", "isNew")
DETAIL_KEYS = ("fields", "timeline", "screenshotUrl")
NEW_FOR = timedelta(hours=24)
WAITING = "Waiting for a reply"
# Confirmation references start with the site, like GH-1001-3F2A.
ATS_PREFIX = {"Greenhouse": "GH", "Ashby": "AB"}


class ApplicationStatus(StrEnum):
    """Where an application stands after it was sent."""

    SUBMITTED = "submitted"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"


class SubmittedBy(StrEnum):
    """Who sent the application."""

    AGENT = "agent"
    YOU = "you"


# ----- reading -----

def application_id(job_id: str) -> str:
    """Return the id of the application made from `job_id`."""
    return f"app-{job_id}"


def is_new(record: dict, now: datetime) -> bool:
    """Return True for an application submitted within the last 24 hours."""
    moment = parse_iso(record.get("submittedAt"))
    return moment is not None and now - moment <= NEW_FOR


def to_summary(record: dict, now: datetime) -> dict:
    """Return the API `Application` (no fields, timeline or screenshotUrl)."""
    out = {key: record.get(key) for key in SUMMARY_KEYS}
    out["isNew"] = is_new(record, now)
    return out


def to_detail(record: dict, now: datetime) -> dict:
    """Return the API `ApplicationDetail`."""
    out = to_summary(record, now)
    out["fields"] = list(record.get("fields") or [])
    out["timeline"] = list(record.get("timeline") or [])
    out["screenshotUrl"] = record.get("screenshotUrl")
    return out


def newest_first(db: Db) -> list[dict]:
    """Return every application, the most recently submitted first."""
    return sorted(db.applications, key=lambda record: record.get("submittedAt") or "",
                  reverse=True)


def find(db: Db, app_id: str) -> dict | None:
    """Return the application with this id, or None."""
    return next((record for record in db.applications if record.get("id") == app_id), None)


def recorded_for(db: Db, job_id: str) -> dict | None:
    """Return the application already made from `job_id`, or None if it isn't submitted yet."""
    job = jobs.find(db, job_id)
    record = find(db, application_id(job_id))
    if job is not None and job.get("state") == JobState.SUBMITTED and record is not None:
        return record
    return None


# ----- changing -----

def set_status(record: dict, status: str | None, now: str) -> None:
    """Change the status: drop `current` events, log it, and wait again for `submitted`."""
    try:
        new_status = ApplicationStatus(status)
    except ValueError:
        names = ", ".join(ApplicationStatus)
        raise ApiError(422, "invalid_status", f"status must be one of: {names}.") from None
    record["status"] = new_status
    record["timeline"] = [event for event in record.get("timeline") or []
                          if event.get("kind") != EventKind.CURRENT]
    kind = EventKind.RED if new_status is ApplicationStatus.REJECTED else EventKind.ACCENT
    record["timeline"].append({"kind": kind, "text": f"You marked it {new_status.capitalize()}",
                               "at": now})
    if new_status is ApplicationStatus.SUBMITTED:
        record["timeline"].append({"kind": EventKind.CURRENT, "text": WAITING,
                                   "at": record.get("submittedAt") or now})


class ApplicationRecorder:
    """Turns jobs into application records, inside one open `store.tx()`."""

    def __init__(self, store: Store, db: Db):
        self.store = store
        self.db = db

    def screenshot(self, *names: str | None) -> str | None:
        """Return the `screenshotUrl` for the first name that is a file in data/screenshots/."""
        for name in names:
            if name and self.store.path("screenshots", name).is_file():
                return screenshot_url(name)
        return None

    def record(self, job: dict, *, submitted_by: SubmittedBy, at: str,  # pylint: disable=too-many-arguments  # record fields
               events: list[dict], confirmation: dict | None = None,
               screenshot: str | None = None) -> dict:
        """Record the application for `job` and mark the job `submitted` (hidden).

        The timeline is the job's own, then `events`.
        """
        record = {
            "id": application_id(job["id"]),
            "jobId": job["id"],
            "company": job.get("company", ""),
            "role": job.get("role", ""),
            "location": job.get("location", ""),
            "ats": job.get("ats"),
            "url": job.get("url", ""),
            "status": ApplicationStatus.SUBMITTED,
            "submittedAt": at,
            "submittedBy": submitted_by,
            "confirmation": confirmation,
            "fields": list(job.get("fields") or []),
            "timeline": list(job.get("timeline") or []) + events,
            "screenshotUrl": screenshot,
        }
        self.db.applications = [existing for existing in self.db.applications
                                if existing.get("id") != record["id"]] + [record]
        job.update(state=JobState.SUBMITTED, phase=None, currentField=None, question=None)
        job["internal"].update(question=None, runId=None, cancelRequested=False)
        jobs.remove_from_queue(self.db, job["id"])
        return record

    def record_confirmed(self, job: dict, result: RunResult,
                         screenshot: str | None = None) -> dict:
        """Record a submit whose thank-you page was seen: a confirmation and a `current` event.

        The screenshot is `screenshot` (a file name) if given, else the one saved after Submit,
        else (that save failed) the ready-time one.
        """
        now = self.store.now_iso()
        link = job["internal"].get("link") or {}
        reference = (f"{ATS_PREFIX.get(job.get('ats'), 'AA')}-{link.get('job_id') or job['id']}"
                     f"-{secrets.token_hex(2).upper()}")
        count = len(result.filled_detail) or len(job.get("fields") or [])
        events = [
            {"kind": EventKind.ACCENT, "text": f"Submitted via {job.get('ats')}, {count} fields. "
                                               "Confirmation page received.", "at": now},
            {"kind": EventKind.CURRENT, "text": WAITING, "at": now},
        ]
        return self.record(job, submitted_by=SubmittedBy.AGENT, at=now, events=events,
                           confirmation={"reference": reference, "confirmedAt": now},
                           screenshot=self.screenshot(screenshot, _after_submit_shot(result),
                                                      job["internal"].get("screenshot")))


def _after_submit_shot(result: RunResult) -> str | None:
    """Return the screenshot saved after Submit, or None when only the filled form's exists."""
    if result.screenshot and result.screenshot != result.filled_screenshot:
        return Path(result.screenshot).name
    return None
