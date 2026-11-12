"""Applications: what a submitted job becomes, and the submit itself (spec 2.11).

A record in `applications.json` is the API `ApplicationDetail` without `isNew` (derived on
read: submitted within the last 24 h), plus the server-only `_resultScreenshot` (the
after-Submit image name, kept but not shown). Ids are `app-<jobId>`.

The job an application comes from stays in `jobs.json` as `submitted` (hidden from GET /jobs).

POST /jobs/:id/submit follows SUBMIT_REAL_FORM:

- off: no browser. The application is a dry run: `confirmation` null, the ready-time
  screenshot, and an amber "Not sent" line instead of a `current` event. It still counts
  toward `sentToday`. The window held since the fill is closed untouched.
- on: the worker presses Submit on the page held open since the fill, then waits up to
  CONFIRM_TIMEOUT_S (default 90 s) for the thank-you page, so the user can type a code the
  site emailed into the visible window. Without a held page it fills the form again first and
  says so on the timeline (`AgentWorker.submit_run`, which never overlaps a fill). The request
  answers once that is done.
"""
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from server import jobs
from server.errors import ApiError, not_found
from server.routes.files import screenshot_url
from server.store import Db, Store, parse_iso

# Keys of the API `Application`, in types.ts order. ApplicationDetail adds DETAIL_KEYS.
SUMMARY_KEYS = ("id", "jobId", "company", "role", "location", "ats", "url", "status",
                "submittedAt", "submittedBy", "confirmation", "isNew")
DETAIL_KEYS = ("fields", "timeline", "screenshotUrl")
STATUSES = ("submitted", "interviewing", "offer", "rejected")
NEW_FOR = timedelta(hours=24)
WAITING = "Waiting for a reply"
DRY_RUN = "Not sent: SUBMIT_REAL_FORM is off, so the agent didn't press Submit (dry run)"
ATS_PREFIX = {"Greenhouse": "GH", "Ashby": "AB"}

NOT_READY = "This job isn’t waiting for review."
NOT_HANDOFF = "This job isn’t waiting for you to finish it."
ANSWERS_CHANGED = ("An answer this form needs is gone from your Answer bank, so the agent "
                   "stopped before Submit. Answer its question, then review it again.")
UNCONFIRMED = ("The agent pressed Submit but didn't see a confirmation page. Check the site "
               "before trying again.")
SUBMIT_CANCELLED = "The submit was stopped before the agent pressed Submit."
REFILLED = ("The review window was gone (closed, or the server restarted), so the agent filled "
            "the form again before pressing Submit")
CODE_UNCONFIRMED = ("{site} asked for the verification code it emailed you, and the agent didn't "
                    "see a confirmation page within {seconds} seconds. Check your email and "
                    "the site: if the application didn't go through, finish it there, then "
                    "mark it submitted.")


# ----- serialization -----

def is_new(record: dict, now: datetime) -> bool:
    moment = parse_iso(record.get("submittedAt"))
    return moment is not None and now - moment <= NEW_FOR


def to_summary(record: dict, now: datetime) -> dict:
    """The API `Application` (no fields, timeline or screenshotUrl)."""
    out = {key: record.get(key) for key in SUMMARY_KEYS}
    out["isNew"] = is_new(record, now)
    return out


def to_detail(record: dict, now: datetime) -> dict:
    """The API `ApplicationDetail`."""
    out = to_summary(record, now)
    out["fields"] = list(record.get("fields") or [])
    out["timeline"] = list(record.get("timeline") or [])
    out["screenshotUrl"] = record.get("screenshotUrl")
    return out


def newest_first(db: Db) -> list[dict]:
    return sorted(db.applications, key=lambda r: r.get("submittedAt") or "", reverse=True)


def find(db: Db, app_id: str) -> dict | None:
    return next((r for r in db.applications if r.get("id") == app_id), None)


# ----- making one -----

def _screenshot(store: Store, name: str | None) -> str | None:
    """The `screenshotUrl` for a file in data/screenshots/, if it is there."""
    if name and store.path("screenshots", name).is_file():
        return screenshot_url(name)
    return None


def from_job(db: Db, job: dict, *, submitted_by: str,  # pylint: disable=too-many-arguments
             at: str, events: list[dict], confirmation: dict | None = None,
             screenshot: str | None = None) -> dict:
    """Records the application for `job` and marks the job `submitted` (hidden).

    The timeline is the job's own, then `events`.
    """
    record = {
        "id": f"app-{job['id']}",
        "jobId": job["id"],
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "location": job.get("location", ""),
        "ats": job.get("ats"),
        "url": job.get("url", ""),
        "status": "submitted",
        "submittedAt": at,
        "submittedBy": submitted_by,
        "confirmation": confirmation,
        "fields": list(job.get("fields") or []),
        "timeline": list(job.get("timeline") or []) + events,
        "screenshotUrl": screenshot,
    }
    db.applications = [r for r in db.applications if r.get("id") != record["id"]] + [record]
    job.update(state="submitted", phase=None, currentField=None, question=None)
    job["internal"].update(question=None, runId=None, cancelRequested=False)
    jobs.remove_from_queue(db, job["id"])
    return record


def _job_in(db: Db, job_id: str, state: str, code: str, message: str) -> dict:
    job = jobs.find(db, job_id)
    if job is None or job.get("state") != state:
        raise ApiError(409, code, message)
    return job


# ----- POST /jobs/:id/submit -----

def submit(store: Store, worker, config, job_id: str) -> dict:
    """Submits a `ready` job; returns the API `Application`. Raises ApiError (spec 2.11)."""
    if not config.submit_real_form:
        with store.tx() as db:
            job = _job_in(db, job_id, "ready", "not_ready", NOT_READY)
            now = store.now_iso()
            record = from_job(db, job, submitted_by="agent", at=now,
                              events=[{"kind": "amber", "text": DRY_RUN, "at": now}],
                              screenshot=_screenshot(store, job["internal"].get("screenshot")))
            summary = to_summary(record, store.now())
        worker.close_form(job_id)  # the held window is never touched in a dry run
        return summary

    with store.tx() as db:  # moving it to running/submitting is the double-submit guard
        job = _job_in(db, job_id, "ready", "not_ready", NOT_READY)
        run_id = worker.claim(job, phase="submitting")
    run = worker.submit_run(job_id, run_id)
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None:
            raise not_found("Job")
        outcome = _after_submit(store, worker, config, db, job, run_id, run)
        if job["internal"].get("runId") == run_id:
            job["internal"].update(runId=None, cancelRequested=False)
    if isinstance(outcome, ApiError):
        raise outcome
    return outcome


def _unconfirmed(job: dict, config, result) -> str:
    """Why the job went to `handoff` after Submit: a code was asked for, or no confirmation."""
    if result.asked_for_code:
        return CODE_UNCONFIRMED.format(site=job.get("ats") or "The site",
                                       seconds=config.confirm_timeout_s)
    return UNCONFIRMED


def _after_submit(store: Store, worker, config, db: Db,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-return-statements,too-many-locals
                  job: dict, run_id: str, run) -> dict | ApiError:
    """Applies a submit run's outcome (a worker SubmitOutcome) to the job: the Application, or
    the error to answer with.

    Errors are returned, not raised, so the job's new state is saved (raising rolls back).
    """
    ctx, result = run.ctx, run.result
    owned = worker.owns(job, run_id)
    now = store.now_iso()
    if run.refilled and ctx is not None:
        jobs.add_event(job, "muted", REFILLED, now)
    if result.status == "submitted":  # the form went out, even if the job was cancelled since
        link = job["internal"].get("link") or {}
        reference = f"{ATS_PREFIX.get(job.get('ats'), 'AA')}-{link.get('job_id') or job['id']}" \
                    f"-{secrets.token_hex(2).upper()}"
        count = len(result.filled_detail) or len(job.get("fields") or [])
        record = from_job(db, job, submitted_by="agent", at=now, events=[
            {"kind": "accent", "text": f"Submitted via {job.get('ats')}, {count} fields. "
                                       "Confirmation page received.", "at": now},
            {"kind": "current", "text": WAITING, "at": now},
        ], confirmation={"reference": reference, "confirmedAt": now},
            screenshot=_screenshot(store, job["internal"].get("screenshot")))
        if result.screenshot and result.screenshot != result.filled_screenshot:
            record["_resultScreenshot"] = Path(result.screenshot).name
        return to_summary(record, store.now())

    pressed = run.pressed
    if not owned:  # cancelled, skipped or wiped meanwhile; leave the job where that put it
        if pressed:
            return ApiError(502, "submit_unconfirmed", _unconfirmed(job, config, result))
        return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
    if result.status == "needs_input" and ctx is not None:
        worker.to_question(db, job, ctx, result)
        return ApiError(409, "answers_changed", ANSWERS_CHANGED)
    if pressed:
        reason = _unconfirmed(job, config, result)
        job.update(state="handoff", phase=None, currentField=None, reason=reason)
        jobs.add_event(job, "amber", reason, now)
        return ApiError(502, "submit_unconfirmed", reason)
    job.update(state="ready", phase=None, currentField=None)
    if result.status == "cancelled":  # the server is shutting down
        return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
    reason = result.reason or "The run didn't finish."
    return ApiError(502, "submit_failed", f"The agent couldn't submit it: {reason} "
                                         "It's still ready for you to try again.")


# ----- POST /jobs/:id/mark-submitted -----

def mark_submitted(store: Store, job_id: str) -> dict:
    """The user finished a `handoff` job on the site; returns the API `Application`."""
    with store.tx() as db:
        job = _job_in(db, job_id, "handoff", "not_handoff", NOT_HANDOFF)
        now = store.now_iso()
        record = from_job(db, job, submitted_by="you", at=now, events=[
            {"kind": "accent", "text": f"You finished it on {job.get('company', '')}’s site",
             "at": now},
            {"kind": "current", "text": WAITING, "at": now},
        ])
        return to_summary(record, store.now())


# ----- PATCH /applications/:id -----

def set_status(record: dict, status: str, now: str) -> None:
    """Like the mock: drop `current` events, log the change, and wait again for `submitted`."""
    if status not in STATUSES:
        raise ApiError(422, "invalid_status",
                       f"status must be one of: {', '.join(STATUSES)}.")
    record["status"] = status
    record["timeline"] = [e for e in record.get("timeline") or [] if e.get("kind") != "current"]
    record["timeline"].append({"kind": "red" if status == "rejected" else "accent",
                               "text": f"You marked it {status.capitalize()}", "at": now})
    if status == "submitted":
        record["timeline"].append({"kind": "current", "text": WAITING,
                                   "at": record.get("submittedAt") or now})
