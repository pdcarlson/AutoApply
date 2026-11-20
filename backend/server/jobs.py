"""Job records in jobs.json: their states, API shape, lookups and the changes routes share."""
from datetime import datetime
from enum import StrEnum

from server.store import Db, iso

# Keys of the API `Job`, in types.ts order. JobDetail adds DETAIL_KEYS.
JOB_KEYS = ("id", "company", "role", "location", "ats", "url", "source", "postedAt", "addedAt",
            "closesOn", "reason", "checks", "skipSuggested", "state", "phase", "progress",
            "formSummary", "question", "readyAt", "asksForCode", "liveView")
DETAIL_KEYS = ("fields", "currentField")
RESTART_HANDOFF_REASON = "The server restarted while submitting; check the site"
RESTART_WINDOW_GONE = ("The server restarted, so the form window closed before the application "
                       "was confirmed. Check your email and the site: if it went through, mark "
                       "it submitted.")
# A run in these phases may already have pressed Submit, so it must never be run again.
SENDING_PHASES = ("submitting", "confirming")


class JobState(StrEnum):
    """Where a job is in its life."""

    OPEN = "open"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    NEEDS_INPUT = "needs_input"
    HANDOFF = "handoff"
    READY = "ready"
    SKIPPED = "skipped"  # hidden from the Inbox, and can be restored
    SUBMITTED = "submitted"  # hidden from the Inbox: it is an Application now


class EventKind(StrEnum):
    """How a timeline event is shown."""

    MUTED = "muted"
    ACCENT = "accent"
    AMBER = "amber"
    RED = "red"
    CURRENT = "current"


HIDDEN_STATES = (JobState.SKIPPED, JobState.SUBMITTED)


# ----- the API shape -----

def asks_for_code(job: dict) -> bool:
    """Return True while the job's open, watched window waits for a code the site emailed."""
    internal = job.get("internal") or {}
    return job.get("state") == JobState.HANDOFF and bool(internal.get("windowWatched")
                                                          and internal.get("askedForCode"))


def live_view(job: dict) -> dict | None:
    """Return where the web app can watch and drive the job's open browser, or None."""
    if not (job.get("internal") or {}).get("liveView"):
        return None
    return {"url": f"/api/jobs/{job['id']}/live"}


def to_api_job(job: dict) -> dict:
    """Return the API `Job`: no fields, currentField, timeline or internal."""
    out = {key: job.get(key) for key in JOB_KEYS}
    out["asksForCode"] = asks_for_code(job)
    out["liveView"] = live_view(job)
    return out


def to_api_job_detail(job: dict) -> dict:
    """Return the API `JobDetail`: the Job plus `fields` and `currentField`."""
    detail = to_api_job(job)
    detail["fields"] = list(job.get("fields") or [])
    detail["currentField"] = job.get("currentField")
    return detail


# ----- lookups -----

def find(db: Db, job_id: str) -> dict | None:
    """Return the record for `job_id` (any state), or None."""
    return next((job for job in db.jobs if job.get("id") == job_id), None)


def visible(job: dict) -> bool:
    """Return True for jobs GET /jobs lists (everything not skipped or submitted)."""
    return job.get("state") not in HIDDEN_STATES


def link_key(link: dict) -> tuple[str, str, str]:
    """Return (site, company, job_id): the identity used for duplicate checks."""
    return (str(link.get("site", "")).lower(), str(link.get("company", "")).lower(),
            str(link.get("job_id", "")))


def find_by_link(db: Db, link: dict) -> dict | None:
    """Return the job record (any state) for the same posting, or None."""
    wanted = link_key(link)
    for job in db.jobs:
        if link_key((job.get("internal") or {}).get("link") or {}) == wanted:
            return job
    return None


# ----- changes -----

def add_event(job: dict, kind: EventKind, text: str, at: str) -> None:
    """Append a TimelineEvent to the job."""
    job.setdefault("timeline", []).append({"kind": kind, "text": text, "at": at})


def remove_from_queue(db: Db, job_id: str) -> None:
    """Take `job_id` out of `state.queue`."""
    db.state["queue"] = [queued_id for queued_id in db.state.get("queue", [])
                         if queued_id != job_id]


def append_to_queue(db: Db, job_id: str) -> None:
    """Put `job_id` last in `state.queue`."""
    remove_from_queue(db, job_id)
    db.state["queue"].append(job_id)


def requeue_at_front(db: Db, job: dict) -> None:
    """Make the job `queued`, first in `state.queue` (after a question, or a restart)."""
    job.update(state=JobState.QUEUED, phase=None, currentField=None)
    job["internal"]["runId"] = None
    job["internal"]["cancelRequested"] = False
    remove_from_queue(db, job["id"])
    db.state["queue"].insert(0, job["id"])


def reset_progress(job: dict) -> None:
    """Clear what a run filled: fields, currentField, phase and progress.filled."""
    job["fields"] = []
    job["currentField"] = None
    job["phase"] = None
    job["progress"] = {**(job.get("progress") or {"total": 0}), "filled": 0}


def stop_run(job: dict) -> None:
    """Detach a running job from its run; the worker sees this and stops at the next field."""
    internal = job["internal"]
    if job.get("state") == JobState.RUNNING:
        internal["cancelRequested"] = True
    internal["runId"] = None


def to_open(job: dict, *, clear_cache: bool) -> None:
    """Send the job back to `open` with no progress and no question (cancel, restore)."""
    stop_run(job)
    reset_progress(job)
    job.update(state=JobState.OPEN, question=None, readyAt=None)
    job["internal"]["question"] = None
    if clear_cache:
        job["internal"]["claudeCache"] = {}


def skip(db: Db, job: dict) -> None:
    """Hide the job (kept for restore) and take it out of the queue."""
    stop_run(job)
    job.update(state=JobState.SKIPPED, phase=None, currentField=None)
    remove_from_queue(db, job["id"])


def restore(job: dict) -> None:
    """Bring a skipped job back as `open`, with no progress, question or Claude cache."""
    to_open(job, clear_cache=True)


# ----- restart recovery -----

def recover_after_restart(db: Db, now: datetime) -> None:
    """Fix the jobs a previous process left mid-run, and make `state.queue` consistent."""
    at = iso(now)
    interrupted = []
    for job in db.jobs:
        _forget_open_windows(job, at)
        if job.get("state") != JobState.RUNNING:
            continue
        if job.get("phase") in SENDING_PHASES:
            _hand_off_interrupted_submit(db, job, at)
        else:
            interrupted.append(job)
    _rebuild_queue(db)
    for job in reversed(interrupted):
        reset_progress(job)
        requeue_at_front(db, job)


def _forget_open_windows(job: dict, at: str) -> None:
    """Every browser ended with the old process: no live view, and no window being watched."""
    internal = job.setdefault("internal", {})
    internal["liveView"] = False
    if internal.get("windowWatched"):
        internal["windowWatched"] = False
        if job.get("state") == JobState.HANDOFF:
            job["reason"] = RESTART_WINDOW_GONE
            add_event(job, EventKind.AMBER, RESTART_WINDOW_GONE, at)


def _hand_off_interrupted_submit(db: Db, job: dict, at: str) -> None:
    """A run stopped while submitting: the form may have been sent, so the person checks."""
    job["internal"]["runId"] = None
    job["internal"]["cancelRequested"] = False
    job.update(state=JobState.HANDOFF, phase=None, currentField=None,
               reason=RESTART_HANDOFF_REASON)
    add_event(job, EventKind.AMBER, RESTART_HANDOFF_REASON, at)
    remove_from_queue(db, job["id"])


def _rebuild_queue(db: Db) -> None:
    """Keep only ids of jobs that really are queued, then add any queued job that is missing."""
    by_id = {job.get("id"): job for job in db.jobs}
    db.state["queue"] = [job_id for job_id in dict.fromkeys(db.state.get("queue", []))
                         if by_id.get(job_id, {}).get("state") == JobState.QUEUED]
    for job in db.jobs:
        if job.get("state") == JobState.QUEUED and job["id"] not in db.state["queue"]:
            db.state["queue"].append(job["id"])
