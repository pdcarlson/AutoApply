"""Job records: state transitions, the queue, the daily limit and serialization (spec 2.9, 2.10).

A job record in `jobs.json` is the API `Job` plus:

    fields        [FilledField]  what the agent filled or plans to fill (JobDetail)
    currentField  str | None     the label being filled right now (JobDetail)
    timeline      [TimelineEvent] kept for the Application made from this job (WP5)
    approvedAt    ISO | None     when the user pressed Apply (orders `waiting` jobs)
    internal      dict           server-only, never sent:
        link            {url, site, company, job_id}  the parsed agent JobLink
        jobData         dict | None  the Greenhouse Job Board API payload cached at add time
        claudeCache     {field key: {value, confidence, reason}}  Claude's guesses for this job
        question        {fieldKey, label, kind, options} | None  the field `question` asks about
        questionCount   int   how many questions this job has asked (ids q-<jobId>-<n>)
        runId           str | None  the run that owns the job while it is `running`
        cancelRequested bool  set by /jobs/cancel or skip; the run stops at the next field
        screenshot      str | None  `<id>-filled.png` from the last fill that reached `ready`
        windowWatched   bool  `handoff` after an unconfirmed Submit whose window stayed open
                              and is watched for the confirmation (gone after a restart)

States: open, queued, running, waiting, needs_input, handoff, ready, plus the server-only
`skipped` (hidden, can be restored) and `submitted` (hidden; WP5 makes the Application).

`state.queue` holds the ids of queued jobs in run order. A job stays in it while it runs and
leaves it when the run ends. Every function here takes the `db` of an open `store.tx()`.
"""
from datetime import datetime

from server.store import Db, iso, parse_iso

# Keys of the API `Job`, in types.ts order. JobDetail adds DETAIL_KEYS.
JOB_KEYS = ("id", "company", "role", "location", "ats", "url", "source", "postedAt", "addedAt",
            "closesOn", "reason", "checks", "skipSuggested", "state", "phase", "progress",
            "formSummary", "question", "readyAt")
DETAIL_KEYS = ("fields", "currentField")

HIDDEN_STATES = ("skipped", "submitted")
# States that hold a place against the daily limit (spec 2.10).
COMMITTED_STATES = ("queued", "running", "needs_input", "ready")
CANCELLABLE_STATES = ("queued", "running", "waiting")
RESTART_HANDOFF_REASON = "The server restarted while submitting; check the site"
RESTART_WINDOW_GONE = ("The server restarted, so the form window closed before the application "
                       "was confirmed. Check your email and the site: if it went through, mark "
                       "it submitted.")


# ----- serialization -----

def to_api_job(job: dict) -> dict:
    """The API `Job`: no fields, currentField, timeline or internal."""
    return {key: job.get(key) for key in JOB_KEYS}


def to_api_job_detail(job: dict) -> dict:
    """The API `JobDetail`: Job plus `fields` and `currentField`."""
    detail = to_api_job(job)
    detail["fields"] = list(job.get("fields") or [])
    detail["currentField"] = job.get("currentField")
    return detail


# ----- lookups -----

def find(db: Db, job_id: str) -> dict | None:
    """The live record for `job_id` (any state), or None."""
    return next((job for job in db.jobs if job.get("id") == job_id), None)


def visible(job: dict) -> bool:
    """True for jobs GET /jobs lists (everything not skipped or submitted)."""
    return job.get("state") not in HIDDEN_STATES


def link_key(link: dict) -> tuple[str, str, str]:
    """(site, company, job_id): the identity used for duplicate checks."""
    return (str(link.get("site", "")).lower(), str(link.get("company", "")).lower(),
            str(link.get("job_id", "")))


def find_by_link(db: Db, link: dict) -> dict | None:
    """The job record (any state) for the same posting, or None."""
    wanted = link_key(link)
    for job in db.jobs:
        if link_key((job.get("internal") or {}).get("link") or {}) == wanted:
            return job
    return None


# ----- small mutations -----

def add_event(job: dict, kind: str, text: str, at: str) -> None:
    """Appends a TimelineEvent (muted, accent, amber, red or current)."""
    job.setdefault("timeline", []).append({"kind": kind, "text": text, "at": at})


def remove_from_queue(db: Db, job_id: str) -> None:
    db.state["queue"] = [jid for jid in db.state.get("queue", []) if jid != job_id]


def append_to_queue(db: Db, job_id: str) -> None:
    remove_from_queue(db, job_id)
    db.state["queue"].append(job_id)


def requeue_at_front(db: Db, job: dict) -> None:
    """`queued`, first in `state.queue` (accept after a question, restart recovery)."""
    job.update(state="queued", phase=None, currentField=None)
    job["internal"]["runId"] = None
    job["internal"]["cancelRequested"] = False
    remove_from_queue(db, job["id"])
    db.state["queue"].insert(0, job["id"])


def reset_progress(job: dict) -> None:
    """Clears what a run filled: fields, currentField, phase and progress.filled."""
    job["fields"] = []
    job["currentField"] = None
    job["phase"] = None
    job["progress"] = {**(job.get("progress") or {"total": 0}), "filled": 0}


def stop_run(job: dict) -> None:
    """Detaches a running job from its run; the worker sees this and stops at the next field."""
    internal = job["internal"]
    if job.get("state") == "running":
        internal["cancelRequested"] = True
    internal["runId"] = None


def to_open(job: dict, *, clear_cache: bool) -> None:
    """Back to `open` with no progress and no question (cancel, restore)."""
    stop_run(job)
    reset_progress(job)
    job.update(state="open", question=None, readyAt=None)
    job["internal"]["question"] = None
    if clear_cache:
        job["internal"]["claudeCache"] = {}


# ----- status and the daily limit -----

def sent_today(db: Db, now: datetime) -> int:
    """Applications the agent sent (dry runs included) whose submittedAt is today, local time."""
    today = now.astimezone().date()
    count = 0
    for app in db.applications:
        if app.get("submittedBy") != "agent":
            continue
        moment = parse_iso(app.get("submittedAt"))
        if moment and moment.astimezone().date() == today:
            count += 1
    return count


def committed(db: Db, now: datetime) -> int:
    """sentToday plus every job that holds a place: queued, running, needs_input or ready."""
    return sent_today(db, now) + sum(1 for job in db.jobs
                                     if job.get("state") in COMMITTED_STATES)


def room(db: Db, now: datetime) -> int:
    """How many more jobs can be queued today."""
    return max(0, int(db.settings["dailyLimit"]) - committed(db, now))


def queue_order(db: Db) -> list[str]:
    """Running ids, then queued ids in state.queue order, then waiting ids by approval time."""
    by_id = {job.get("id"): job for job in db.jobs}
    running = [job["id"] for job in db.jobs if job.get("state") == "running"]
    queued = [jid for jid in db.state.get("queue", [])
              if by_id.get(jid, {}).get("state") == "queued"]
    return running + queued + [job["id"] for job in _waiting(db)]


def agent_status(db: Db, now: datetime) -> dict:
    """The API `AgentStatus`."""
    return {
        "paused": bool(db.state.get("paused")),
        "sentToday": sent_today(db, now),
        "dailyLimit": db.settings["dailyLimit"],
        "queue": queue_order(db),
    }


def _waiting(db: Db) -> list[dict]:
    return sorted((job for job in db.jobs if job.get("state") == "waiting"),
                  key=lambda job: job.get("approvedAt") or "")


def apply(db: Db, job_ids: list[str], now: datetime) -> tuple[list[str], list[str]]:
    """POST /jobs/apply: the first `room` open jobs are queued, the rest wait.

    Ids that aren't `open` (or don't exist) are ignored. Returns (queued, deferred).
    """
    free = room(db, now)
    at = iso(now)
    queued, deferred = [], []
    seen = set()
    for job_id in job_ids:
        job = find(db, job_id)
        if job is None or job_id in seen or job.get("state") != "open":
            continue
        seen.add(job_id)
        job["approvedAt"] = at
        add_event(job, "muted", "You pressed Apply", at)
        if len(queued) < free:
            job["state"] = "queued"
            append_to_queue(db, job_id)
            queued.append(job_id)
        else:
            job["state"] = "waiting"
            deferred.append(job_id)
    return queued, deferred


def promote_waiting(db: Db, now: datetime) -> list[str]:
    """Queues the oldest `waiting` jobs while the daily limit has room. Returns their ids."""
    promoted = []
    free = room(db, now)
    for job in _waiting(db):
        if free <= 0:
            break
        job["state"] = "queued"
        append_to_queue(db, job["id"])
        promoted.append(job["id"])
        free -= 1
    return promoted


def cancel(db: Db, job_ids: list[str]) -> list[str]:
    """POST /jobs/cancel: queued, running or waiting jobs go back to `open`. Returns their ids.

    A running job is detached from its run (cancelRequested) and is `open` right away; the
    worker stops between fields and leaves it alone.
    """
    cancelled = []
    for job_id in job_ids:
        job = find(db, job_id)
        if job is None or job.get("state") not in CANCELLABLE_STATES:
            continue
        to_open(job, clear_cache=True)
        remove_from_queue(db, job_id)
        cancelled.append(job_id)
    return cancelled


def skip(db: Db, job: dict) -> None:
    """Hides the job (kept for restore) and takes it out of the queue."""
    stop_run(job)
    job["state"] = "skipped"
    job["phase"] = None
    job["currentField"] = None
    remove_from_queue(db, job["id"])


def restore(job: dict) -> None:
    """A skipped job comes back as `open`, with no progress, question or Claude cache."""
    to_open(job, clear_cache=True)


# ----- restart recovery (spec 2.3) -----

def recover_after_restart(db: Db, now: datetime) -> None:
    """Fixes jobs a previous process left mid-run, and makes `state.queue` consistent.

    - `running` while filling (or opening) -> `queued`, first in the queue, fields cleared.
    - `running` while submitting or confirming -> `handoff`: the form may have been sent.
    - `handoff` whose open window was being watched for the confirmation: the window is gone
      (it ended with the old process), and the reason says so.
    """
    at = iso(now)
    interrupted = []
    for job in db.jobs:
        job.setdefault("internal", {})
        if job["internal"].get("windowWatched"):
            job["internal"]["windowWatched"] = False
            if job.get("state") == "handoff":
                job["reason"] = RESTART_WINDOW_GONE
                add_event(job, "amber", RESTART_WINDOW_GONE, at)
        if job.get("state") != "running":
            continue
        if job.get("phase") in ("submitting", "confirming"):
            job["internal"]["runId"] = None
            job["internal"]["cancelRequested"] = False
            job.update(state="handoff", phase=None, currentField=None,
                       reason=RESTART_HANDOFF_REASON)
            add_event(job, "amber", RESTART_HANDOFF_REASON, at)
            remove_from_queue(db, job["id"])
        else:
            interrupted.append(job)
    # Keep the queue to ids of jobs that are actually queued, then add any that went missing.
    by_id = {job.get("id"): job for job in db.jobs}
    db.state["queue"] = [jid for jid in dict.fromkeys(db.state.get("queue", []))
                         if by_id.get(jid, {}).get("state") == "queued"]
    for job in db.jobs:
        if job.get("state") == "queued" and job["id"] not in db.state["queue"]:
            db.state["queue"].append(job["id"])
    for job in reversed(interrupted):
        reset_progress(job)
        requeue_at_front(db, job)
