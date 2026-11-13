"""Applications: what a submitted job becomes, and the submit itself (spec 2.11).

A record in `applications.json` is the API `ApplicationDetail` without `isNew` (derived on
read: submitted within the last 24 h). Ids are `app-<jobId>`. Its `screenshotUrl` is the page
after Submit (the thank-you page) when there is one; only a dry run, which never pressed
Submit, shows the ready-time image of the filled form.

The job an application comes from stays in `jobs.json` as `submitted` (hidden from GET /jobs).

POST /jobs/:id/submit follows SUBMIT_REAL_FORM:

- off: no browser. The application is a dry run: `confirmation` null, the ready-time
  screenshot, and an amber "Not sent" line instead of a `current` event. It still counts
  toward `sentToday`. The window held since the fill stays open, untouched (nothing was sent,
  so it isn't closed; the person closes it).
- on: the worker presses Submit on the page held open since the fill, then waits up to
  CONFIRM_TIMEOUT_S (default 90 s) for the thank-you page, so the user can type a code the
  site emailed into the visible window. Without a held page it fills the form again first and
  says so on the timeline (`AgentWorker.submit_run`, which never overlaps a fill). The request
  answers once that is done. No confirmation by then: the job goes to `handoff`, but the window
  stays open and is watched with no time limit; when the thank-you page shows up the
  application is recorded just like this (`record_confirmed`), and only then is it closed.

When the site asks for a code it emailed, the wait stops right away (no confirmation can come
until someone types it): the job goes to `handoff` with `asksForCode`, and the user types the
code into the app. POST /jobs/:id/verification-code { code } has the agent type it into the
watched window and send it, then answers with the Application once the thank-you page shows
up, or with `422 code_rejected` (the window keeps asking, so another code can be tried).

POST /jobs/:id/mark-submitted on a job whose window is still open saves a screenshot of that
window first (as the application's screenshot), and only then closes it. If the window shows
the thank-you page at that moment and the agent pressed Submit there, it is recorded as a
confirmed submit.
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
WATCHING_CODE = ("{site} emailed you a verification code to finish this application. Find "
                 "the email and enter the code here: the agent types it into the form and "
                 "submits it.")
NO_CODE = "Enter the code from the email."
NO_CODE_WINDOW = ("This job isn’t waiting for an emailed code anymore. Check the site, and mark "
                  "it submitted if it went through.")
WATCHING = ("The agent pressed Submit but hasn't seen a confirmation page yet. The form window "
            "stays open: finish it there — the agent will record the application as soon as "
            "the thank-you page appears.")
WINDOW_CLOSED = ("The form window was closed before the application was confirmed. Check your "
                 "email and the site: if it went through, mark it submitted.")
HIDDEN_WINDOW = (" (The agent's browser is hidden because AGENT_SHOW_BROWSER is off: check your "
                 "email and the site, then mark it submitted.)")


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

def _screenshot(store: Store, *names: str | None) -> str | None:
    """The `screenshotUrl` for the first of `names` that is a file in data/screenshots/."""
    for name in names:
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


def record_confirmed(store: Store, db: Db, job: dict, result,  # pylint: disable=too-many-arguments
                     screenshot: str | None = None) -> dict:
    """Records a confirmed submit (the thank-you page was seen): confirmation, `current` event.

    `result` is the submit's RunResult. The application's screenshot is `screenshot` (a file
    name in data/screenshots/) if given, else the one saved after Submit, else (that save
    failed) the ready-time one.
    """
    now = store.now_iso()
    link = job["internal"].get("link") or {}
    reference = f"{ATS_PREFIX.get(job.get('ats'), 'AA')}-{link.get('job_id') or job['id']}" \
                f"-{secrets.token_hex(2).upper()}"
    count = len(result.filled_detail) or len(job.get("fields") or [])
    record = from_job(db, job, submitted_by="agent", at=now, events=[
        {"kind": "accent", "text": f"Submitted via {job.get('ats')}, {count} fields. "
                                   "Confirmation page received.", "at": now},
        {"kind": "current", "text": WAITING, "at": now},
    ], confirmation={"reference": reference, "confirmedAt": now},
        screenshot=_screenshot(store, screenshot, _after_submit_shot(result),
                               job["internal"].get("screenshot")))
    return record


def _after_submit_shot(result) -> str | None:
    """The file name of the screenshot saved after Submit, or None if it wasn't saved
    (`result.screenshot` is then still the filled-form one)."""
    if result.screenshot and result.screenshot != result.filled_screenshot:
        return Path(result.screenshot).name
    return None


def watching_reason(job: dict, config, asked_for_code: bool) -> str:
    """Why the job is in `handoff` while its open window is watched for the confirmation."""
    if asked_for_code:  # typed in through the app, so a hidden browser doesn't matter
        return WATCHING_CODE.format(site=job.get("ats") or "The site")
    return WATCHING if config.show_browser else WATCHING + HIDDEN_WINDOW


def watch(job: dict, session, result) -> None:
    """Notes on the job whether its window is open and watched, and asks for an emailed code."""
    watched = bool(session is not None and session.alive and not result.window_closed)
    job["internal"]["windowWatched"] = watched
    job["internal"]["askedForCode"] = watched and bool(result.asked_for_code)


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
            return to_summary(record, store.now())  # the held window stays open, untouched

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


def _unconfirmed(job: dict, config, run) -> str:
    """Why the job went to `handoff` after Submit: its window is still open and watched, or it
    was closed, or (no window left) no confirmation was seen."""
    result = run.result
    if result.window_closed:
        return WINDOW_CLOSED
    session = run.ctx.session if run.ctx is not None else None
    if session is not None and session.alive:
        return watching_reason(job, config, result.asked_for_code)
    return UNCONFIRMED


def _after_submit(store: Store, worker, config, db: Db,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-return-statements,too-many-locals
                  job: dict, run_id: str, run) -> dict | ApiError:
    """Applies a submit run's outcome (a worker SubmitOutcome) to the job: the Application, or
    the error to answer with.

    Errors are returned, not raised, so the job's new state is saved (raising rolls back).
    """
    ctx, result = run.ctx, run.result
    existing = find(db, f"app-{job['id']}")
    if job.get("state") == "submitted" and existing is not None:
        return to_summary(existing, store.now())  # its window saw the confirmation meanwhile
    owned = worker.owns(job, run_id)
    now = store.now_iso()
    if run.refilled and ctx is not None:
        jobs.add_event(job, "muted", REFILLED, now)
    if result.status == "submitted":  # the form went out, even if the job was cancelled since
        return to_summary(record_confirmed(store, db, job, result), store.now())

    pressed = run.pressed
    if not owned:  # cancelled, skipped or wiped meanwhile; leave the job where that put it
        if pressed:
            return ApiError(502, "submit_unconfirmed", _unconfirmed(job, config, run))
        return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
    if result.status == "needs_input" and ctx is not None:
        worker.to_question(db, job, ctx, result)
        return ApiError(409, "answers_changed", ANSWERS_CHANGED)
    if pressed:
        reason = _unconfirmed(job, config, run)
        job.update(state="handoff", phase=None, currentField=None, reason=reason)
        watch(job, ctx.session if ctx is not None else None, result)
        jobs.add_event(job, "amber", reason, now)
        return ApiError(502, "submit_unconfirmed", reason)
    job.update(state="ready", phase=None, currentField=None)
    if result.status == "cancelled":  # the server is shutting down
        return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
    reason = result.reason or "The run didn't finish."
    return ApiError(502, "submit_failed", f"The agent couldn't submit it: {reason} "
                                         "It's still ready for you to try again.")


# ----- POST /jobs/:id/verification-code -----

def enter_code(store: Store, worker, job_id: str, code) -> dict:
    """The agent types the code the site emailed into the job's watched window and sends it.

    Returns the API `Application` once the thank-you page shows up. Not taken: `422
    code_rejected`, and the job stays in `handoff`, still asking. Doesn't wait for other
    browser runs (the code can expire meanwhile): the window is driven on its own thread.
    """
    code = "".join(str(code or "").split())
    if not code:
        raise ApiError(422, "invalid_code", NO_CODE)
    with store.tx() as db:
        job = jobs.find(db, job_id)
        existing = find(db, f"app-{job_id}")
        if job is not None and job.get("state") == "submitted" and existing is not None:
            return to_summary(existing, store.now())  # its window recorded it a moment ago
        job = _job_in(db, job_id, "handoff", "not_handoff", NOT_HANDOFF)
        if not jobs.asks_for_code(job):
            raise ApiError(409, "no_code_window", NO_CODE_WINDOW)
    session = worker.held_form(job_id)
    result = session.enter_code(code) if session is not None and session.watching else None
    with store.tx() as db:
        job = jobs.find(db, job_id)
        existing = find(db, f"app-{job_id}")
        if job is not None and job.get("state") == "submitted" and existing is not None:
            return to_summary(existing, store.now())
        if job is None:
            raise not_found("Job")
        if result is not None and result.status == "submitted":  # sent, whatever happened since
            return to_summary(record_confirmed(store, db, job, result), store.now())
        error = _code_not_taken(store, job, result)
    raise error


def _code_not_taken(store: Store, job: dict, result) -> ApiError:
    """Updates a job whose code didn't confirm it; returns the error to answer with."""
    now = store.now_iso()
    if result is not None and result.asked_for_code and not result.window_closed:
        jobs.add_event(job, "amber",
                       f"{job.get('ats') or 'The site'} didn’t take the code you entered", now)
        return ApiError(422, "code_rejected", result.reason)
    # The window is gone (its close handler already said so), or it stopped asking for a code.
    if job.get("state") == "handoff":
        job["internal"]["askedForCode"] = False
        if result is None or not result.window_closed:
            job["reason"] = NO_CODE_WINDOW
            jobs.add_event(job, "amber", NO_CODE_WINDOW, now)
    closed = result is not None and result.window_closed
    return ApiError(409, "no_code_window", WINDOW_CLOSED if closed else NO_CODE_WINDOW)


# ----- POST /jobs/:id/mark-submitted -----

def _final_look(held) -> tuple[str | None, bool]:
    """On the session thread: (saved screenshot path or None, shows the thank-you page)."""
    confirmed = held.confirmed()
    return (str(held.result_shot) if held.save_screenshot() else None), confirmed


def mark_submitted(store: Store, worker, job_id: str) -> dict:
    """The user finished a `handoff` job on the site; returns the API `Application`.

    A window still open for the job is screenshotted first (the application's screenshot);
    only once that is saved and the application recorded is the window closed.
    """
    with store.tx() as db:
        job = jobs.find(db, job_id)
        existing = find(db, f"app-{job_id}")
        if job is not None and job.get("state") == "submitted" and existing is not None:
            return to_summary(existing, store.now())  # its window recorded it a moment ago
        _job_in(db, job_id, "handoff", "not_handoff", NOT_HANDOFF)
    session = worker.held_form(job_id)
    shot, confirmed = None, False
    if session is not None:
        try:
            shot, confirmed = session.call(_final_look)
        except Exception:  # pylint: disable=broad-except
            session = None  # closed meanwhile: nothing to screenshot or close
    with store.tx() as db:
        job = jobs.find(db, job_id)
        existing = find(db, f"app-{job_id}")
        if job is not None and job.get("state") == "submitted" and existing is not None:
            record = existing
        else:
            job = _job_in(db, job_id, "handoff", "not_handoff", NOT_HANDOFF)
            name = Path(shot).name if shot else None
            if confirmed and session is not None and session.pressed:
                result = session.submit_result
                record = record_confirmed(store, db, job, result, screenshot=name)
            else:
                now = store.now_iso()
                record = from_job(db, job, submitted_by="you", at=now, events=[
                    {"kind": "accent",
                     "text": f"You finished it on {job.get('company', '')}’s site", "at": now},
                    {"kind": "current", "text": WAITING, "at": now},
                ], screenshot=_screenshot(store, name))
        summary = to_summary(record, store.now())
    if session is not None and shot is not None:
        session.close()  # submitted, and the screenshot is saved
    return summary


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
