"""Writes what a run (or a held window) ended with onto its job record."""
import logging
from pathlib import Path

from agent.runner.apply_run import RunResult
from server import jobs, questions
from server.answer_bank import AnswerBank
from server.applications import reasons
from server.applications.records import ApplicationRecorder
from server.config import Config
from server.jobs import EventKind, JobState
from server.runs.form_session import FormSession
from server.runs.run_context import RunContext
from server.store import Db, Store

log = logging.getLogger(__name__)

SITE_NAMES = {"greenhouse": "Greenhouse", "ashby": "Ashby", "lever": "Lever"}
MISSING_RESUME = "This form needs a resume. Add one on your Profile page."
HELD = "Filled and held for your review"
REUSED = "Still filled in its open window, and held for your review"
WINDOW_CLOSED_READY = "You closed the form window; Submit will fill the form again first"


class JobOutcomes:
    """Moves a job to the state its run's result calls for. Each method runs inside a tx."""

    def __init__(self, store: Store, bank: AnswerBank, config: Config):
        self.store = store
        self.bank = bank
        self.config = config

    def apply_result(self, db: Db, job: dict, ctx: RunContext, result: RunResult) -> None:
        """Apply the result of a first fill (which never presses Submit)."""
        if result.status == "needs_input":
            self.to_question(db, job, ctx, result)
        elif result.status == "ready":
            self.to_ready(db, job, ctx, result)
        elif result.status == "handoff":
            self.to_protected(db, job, ctx, result)
        elif result.status == "cancelled":
            # The run still owns the job, so the worker is shutting down: put it back in line.
            jobs.reset_progress(job)
            jobs.requeue_at_front(db, job)
        else:
            self.to_failed(db, job, result.reason or "The run didn't finish.")

    def to_question(self, db: Db, job: dict, ctx: RunContext, result: RunResult) -> None:
        """Park the job on the run's first unanswered field (`needs_input`)."""
        form_field = result.questions[0]
        if form_field.kind == "file":
            if form_field.profile_key == "resume_path" and not ctx.profile.resume_path:
                self.to_failed(db, job, MISSING_RESUME)
            else:
                self.to_handoff(db, job, "This form needs a file the agent doesn't have: "
                                         f"{form_field.label}")
            return
        internal = job["internal"]
        internal["questionCount"] = int(internal.get("questionCount") or 0) + 1
        guess = ctx.answerer.claude_answers.get(form_field.key)
        question, internal["question"] = questions.make_question(
            job["id"], internal["questionCount"], form_field, guess)
        planned = ctx.sources.from_answered(result.answered)
        total = len(ctx.fields) or len(result.answered) + len(result.questions)
        job.update(state=JobState.NEEDS_INPUT, phase=None, currentField=None, question=question,
                   fields=planned, progress={"filled": len(planned), "total": total})
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, EventKind.AMBER, f"Paused on a question: {form_field.label}",
                       self.store.now_iso())

    def to_ready(self, db: Db, job: dict, ctx: RunContext, result: RunResult,
                 is_reused: bool = False) -> None:
        """Mark the job `ready` for review with what the run filled.

        A reused window was counted in the Answer bank when it was first filled.
        """
        now = self.store.now_iso()
        filled = ctx.filled_fields(result)
        count = len(filled)
        job.update(state=JobState.READY, readyAt=now, phase=None, currentField=None,
                   question=None, fields=filled, progress={"filled": count, "total": count})
        job["internal"]["question"] = None
        job["internal"]["screenshot"] = _file_name(result.filled_screenshot)
        if not is_reused:
            for label, _value, source, _confidence in result.filled_detail:
                record = ctx.sources.record_for(label) if source == "saved" else None
                if record is not None:
                    self.bank.record_use(record["id"], ctx.company, label)
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, EventKind.MUTED, REUSED if is_reused else HELD, now)

    def to_protected(self, db: Db, job: dict, ctx: RunContext, result: RunResult) -> None:
        """Hand off a form with a protected step: the rest is filled and its window held."""
        filled = ctx.filled_fields(result)
        count = len(filled)
        self.to_handoff(db, job, reasons.protected_reason(self.config, result))
        job.update(fields=filled, progress={"filled": count,
                                            "total": count + len(result.protected)})
        job["internal"]["screenshot"] = _file_name(result.filled_screenshot)
        job["internal"].update(windowWatched=result.held is not None, askedForCode=False)

    def to_handoff(self, db: Db, job: dict, reason: str) -> None:
        """Hand the job to the person to finish (`handoff`), saying why."""
        job.update(state=JobState.HANDOFF, phase=None, currentField=None, question=None,
                   reason=reason)
        job["internal"]["question"] = None
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, EventKind.AMBER, reason, self.store.now_iso())

    def to_failed(self, db: Db, job: dict, reason: str) -> None:
        """Send the job back to `open` (there is no failed state) with a `bad` check."""
        jobs.reset_progress(job)
        checks = [check for check in job.get("checks") or [] if check.get("status") != "bad"]
        job.update(state=JobState.OPEN, question=None,
                   checks=[{"status": "bad", "text": reason}] + checks,
                   reason=f"Last try didn't finish: {reason}")
        job["internal"]["question"] = None
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, EventKind.RED, f"Last try didn't finish: {reason}",
                       self.store.now_iso())

    def to_unsupported(self, db: Db, job: dict) -> None:
        """Hand off a job on a site the agent can't fill."""
        site = (job["internal"].get("link") or {}).get("site", "")
        self.to_handoff(db, job,
                        f"AutoApply can't fill {SITE_NAMES.get(site, site.title())} forms yet")

    def back_on_held_window(self, db: Db, job: dict, session: FormSession) -> None:
        """Put a job applied to again back where its still-open window left it.

        A window that was already submitted and waits for its confirmation goes back to
        `handoff`, not `ready`: the form may have been sent.
        """
        job["internal"].update(runId=None, cancelRequested=False)
        if session.watching and not session.pressed:  # held for a protected step
            self.to_protected(db, job, session.context, session.result)
        elif session.watching:
            result = session.submit_result
            self.to_handoff(db, job, reasons.watching_reason(job, self.config, result))
            job["internal"]["windowWatched"] = True
            job["internal"]["askedForCode"] = bool(result and result.asked_for_code)
        else:
            jobs.reset_progress(job)
            self.to_ready(db, job, session.context, session.result, is_reused=True)

    # ----- held windows (called on their session threads) -----

    def window_confirmed(self, session: FormSession, result: RunResult) -> bool:
        """Record the application of a watched window that now shows the thank-you page.

        Returns False when there is nothing to record (the job is gone or already recorded).
        """
        with self.store.tx() as db:
            job = jobs.find(db, session.job_id)
            if job is None or job.get("state") == JobState.SUBMITTED:
                return False
            ApplicationRecorder(self.store, db).record_confirmed(job, result)
        log.info("Job %s: the confirmation showed up in its window; recorded", session.job_id)
        return True

    def window_closed(self, session: FormSession) -> None:
        """Say on the job that the person closed its held window, if that still matters."""
        with self.store.tx() as db:
            job = jobs.find(db, session.job_id)
            if job is None:
                return
            now = self.store.now_iso()
            if job.get("state") == JobState.HANDOFF and session.watching:
                job["reason"] = reasons.WINDOW_CLOSED
                job["internal"]["windowWatched"] = False
                jobs.add_event(job, EventKind.AMBER, reasons.WINDOW_CLOSED, now)
            elif job.get("state") == JobState.READY:
                jobs.add_event(job, EventKind.MUTED, WINDOW_CLOSED_READY, now)


def _file_name(path: str | None) -> str | None:
    """Return the file name of a saved screenshot, or None."""
    return Path(path).name if path else None
