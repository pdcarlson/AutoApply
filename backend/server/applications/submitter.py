"""POST /jobs/:id/submit: sends a `ready` job, or records a dry run when real submits are off."""
from server import jobs
# records is imported as a module: it imports the routes package, which imports this file.
from server.applications import reasons, records
from server.config import Config
from server.errors import ApiError, not_found
from server.jobs import EventKind, JobState
from server.runs.run_events import owns
from server.store import Db, Store

NOT_READY = "This job isn’t waiting for review."
DRY_RUN = "Not sent: SUBMIT_REAL_FORM is off, so the agent didn't press Submit (dry run)"
ANSWERS_CHANGED = ("An answer this form needs is gone from your Answer bank, so the agent "
                   "stopped before Submit. Answer its question, then review it again.")
SUBMIT_CANCELLED = "The submit was stopped before the agent pressed Submit."
REFILLED = ("The review window was gone (closed, or the server restarted), so the agent filled "
            "the form again before pressing Submit")
PROTECTED_STEP = "This form has a step only you can do, so the agent didn't press Submit."


class Submitter:  # pylint: disable=too-few-public-methods  # one entry point: submit
    """Submits `ready` jobs through the worker, and turns the outcome into an Application.

    With SUBMIT_REAL_FORM on, the worker presses Submit on the window held open since the fill
    (or fills the form again first) and waits for the thank-you page. Off, nothing is sent: the
    application is a dry run and the held window stays open, untouched.
    """

    def __init__(self, store: Store, worker, config: Config):
        self.store = store
        self.worker = worker
        self.config = config

    def submit(self, job_id: str) -> dict:
        """Submit a `ready` job and return the API `Application`, or raise ApiError."""
        if not self.config.submit_real_form:
            return self._dry_run(job_id)
        # Moving the job to running/submitting is what stops a second submit.
        with self.store.tx() as db:
            run_id = self.worker.claim(self._ready_job(db, job_id), phase="submitting")
        run = self.worker.submit_run(job_id, run_id)
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is None:
                raise not_found("Job")
            outcome = self._apply_outcome(db, job, run_id, run)
            if job["internal"].get("runId") == run_id:
                job["internal"].update(runId=None, cancelRequested=False)
        # Raised only now, after the tx: raising inside it would roll back the job's new state.
        if isinstance(outcome, ApiError):
            raise outcome
        return outcome

    def _ready_job(self, db: Db, job_id: str) -> dict:
        """Return the job if it is `ready`, or raise 409 not_ready."""
        job = jobs.find(db, job_id)
        if job is None or job.get("state") != JobState.READY:
            raise ApiError(409, "not_ready", NOT_READY)
        return job

    def _dry_run(self, job_id: str) -> dict:
        """Record the application without pressing Submit (SUBMIT_REAL_FORM off)."""
        with self.store.tx() as db:
            job = self._ready_job(db, job_id)
            now = self.store.now_iso()
            recorder = records.ApplicationRecorder(self.store, db)
            record = recorder.record(
                job, submitted_by=records.SubmittedBy.AGENT, at=now,
                events=[{"kind": EventKind.AMBER, "text": DRY_RUN, "at": now}],
                screenshot=recorder.screenshot(job["internal"].get("screenshot")))
            return records.to_summary(record, self.store.now())

    def _apply_outcome(self, db: Db, job: dict, run_id: str, run) -> dict | ApiError:
        """Apply a submit run's outcome to the job: the Application, or the error to answer."""
        existing = records.recorded_for(db, job["id"])
        if existing is not None:  # its window saw the confirmation meanwhile
            return records.to_summary(existing, self.store.now())
        is_owned = owns(job, run_id)
        if run.refilled and run.ctx is not None:
            jobs.add_event(job, EventKind.MUTED, REFILLED, self.store.now_iso())
        if run.result.status == "submitted":  # the form went out, even if cancelled since
            record = records.ApplicationRecorder(self.store, db).record_confirmed(job, run.result)
            return records.to_summary(record, self.store.now())
        if not is_owned:  # cancelled, skipped or wiped meanwhile: leave the job where it is
            if run.pressed:
                return ApiError(502, "submit_unconfirmed", self._unconfirmed_reason(job, run))
            return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
        return self._not_sent(db, job, run)

    def _not_sent(self, db: Db, job: dict, run) -> ApiError:
        """Put a job whose submit didn't go through where it belongs; return the error."""
        ctx, result = run.ctx, run.result
        if result.status == "needs_input" and ctx is not None:
            self.worker.outcomes.to_question(db, job, ctx, result)
            return ApiError(409, "answers_changed", ANSWERS_CHANGED)
        if result.status == "handoff" and ctx is not None:  # the new fill found a protected step
            self.worker.outcomes.to_protected(db, job, ctx, result)
            return ApiError(409, "protected_step", PROTECTED_STEP)
        if run.pressed:
            reason = self._unconfirmed_reason(job, run)
            job.update(state=JobState.HANDOFF, phase=None, currentField=None, reason=reason)
            _note_watched_window(job, ctx.session if ctx is not None else None, result)
            jobs.add_event(job, EventKind.AMBER, reason, self.store.now_iso())
            return ApiError(502, "submit_unconfirmed", reason)
        job.update(state=JobState.READY, phase=None, currentField=None)
        if result.status == "cancelled":  # the server is shutting down
            return ApiError(409, "submit_cancelled", SUBMIT_CANCELLED)
        reason = result.reason or "The run didn't finish."
        return ApiError(502, "submit_failed", f"The agent couldn't submit it: {reason} "
                                              "It's still ready for you to try again.")

    def _unconfirmed_reason(self, job: dict, run) -> str:
        """Return why the job waits after Submit: its window is watched, closed, or gone."""
        result = run.result
        if result.window_closed:
            return reasons.WINDOW_CLOSED
        session = run.ctx.session if run.ctx is not None else None
        if session is not None and session.alive:
            return reasons.watching_reason(job, self.config, result)
        return reasons.UNCONFIRMED


def _note_watched_window(job: dict, session, result) -> None:
    """Note on the job whether its window is open and watched, and whether it wants a code."""
    is_watched = bool(session is not None and session.alive and not result.window_closed)
    job["internal"]["windowWatched"] = is_watched
    job["internal"]["askedForCode"] = is_watched and bool(result.asked_for_code)
