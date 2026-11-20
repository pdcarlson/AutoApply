"""The AgentWorker: a background thread that fills queued jobs one at a time."""
import logging
import threading

from agent.jobs.job_link import UnsupportedLink
from agent.runner.apply_run import RunResult
from server import jobs
from server.answer_bank import AnswerBank
from server.config import Config
from server.job_queue import JobQueue
from server.jobs import JobState
from server.live.live_views import LiveViews
from server.runs.form_session import FormSession, SessionHooks
from server.runs.held_forms import HeldForms
from server.runs.job_outcomes import JobOutcomes
from server.runs.run_context import RunContext, SubmitOutcome
from server.runs.run_events import RunEvents, owns
from server.runs.run_gate import RunGate
from server.runs.run_setup import RunSetup
from server.runs.submit_runs import SubmitRuns
from server.store import Store, new_id

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
STOP_TIMEOUT_SECONDS = 30.0


class AgentWorker:  # pylint: disable=too-many-instance-attributes  # it wires its helpers together
    """Works one user's queue: each queued job is filled up to review, never submitted.

    A fill ends `needs_input`, `handoff`, `ready` or (on failure) `open`. Each fill runs on its
    own FormSession thread, which keeps a filled window open for review while the worker moves
    on. Claiming a job gives it a run id; cancel, skip and deleting the account detach the job
    from it, and the run stops before its next field and drops its result.
    """

    def __init__(self, store: Store, bank: AnswerBank, config: Config,
                 poll_seconds: float = POLL_SECONDS,
                 run_slots: threading.Semaphore | None = None):
        self.store = store
        self.config = config
        self.poll_seconds = poll_seconds
        self.forms = HeldForms()  # filled forms held open for review, by job id
        self.live = LiveViews()  # the open browser pages, by job id, for the live view
        self.setup = RunSetup(store, bank, config)
        self.outcomes = JobOutcomes(store, bank, config)
        self.stopping = threading.Event()
        # Shared by every user's worker: how many runs may go at once on this machine.
        self._run_slots = run_slots or threading.Semaphore(1)
        self._gate = RunGate(self._run_slots)
        self._events = RunEvents(store, self.live)
        self._submits = SubmitRuns(self, self._gate)
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._active: set[str] = set()  # run ids in progress (fill or submit)
        self._cancelled: set[str] = set()  # run ids cancel_current() stopped

    # ----- thread lifecycle -----

    def start(self) -> None:
        """Start the background thread, unless it already runs."""
        if self._thread is not None and self._thread.is_alive():
            return
        self.stopping.clear()
        self._thread = threading.Thread(target=self._loop, name="agent-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the loop; a run in progress stops at its next field and goes back in line.

        Held windows are left alone: they go away with the process (Chromium is its child).
        """
        self.stopping.set()
        self._wake.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(STOP_TIMEOUT_SECONDS)

    def wake(self) -> None:
        """Look at the queue now instead of at the next poll."""
        self._wake.set()

    @property
    def alive(self) -> bool:
        """Return True while the background thread runs."""
        return self._thread is not None and self._thread.is_alive()

    def cancel_current(self) -> None:
        """Ask every run in progress to stop at the next field (DELETE /account)."""
        self._cancelled.update(self._active)

    def held_form(self, job_id: str) -> FormSession | None:
        """Return the live session holding the job's filled window, or None."""
        return self.forms.get(job_id)

    def close_forms(self) -> None:
        """Close every held window: the account was deleted, and nobody else ever could."""
        self.forms.close_all()

    def close_forms_for_tests(self) -> None:
        """Close every held window so no Chromium outlives a test."""
        self.forms.close_all()

    def _loop(self) -> None:
        """Run queued jobs until stopped, waiting for a wake or the next poll in between."""
        while not self.stopping.is_set():
            try:
                while not self.stopping.is_set() and self.run_next():
                    pass
            except Exception:  # pylint: disable=broad-except  # the worker must keep going
                log.exception("The agent worker hit an error; it keeps going")
            self._wake.wait(self.poll_seconds)
            self._wake.clear()

    # ----- picking and claiming -----

    def claim(self, job: dict, phase: str = "opening") -> str:
        """Mark `job` running and owned by a new run; return the run id.

        Call inside the `store.tx()` that checked the job's state, so the move is atomic.
        """
        run_id = new_id("run")
        job.update(state=JobState.RUNNING, phase=phase, currentField=None)
        job["internal"]["runId"] = run_id
        job["internal"]["cancelRequested"] = False
        self._active.add(run_id)
        return run_id

    def run_next(self) -> str | None:
        """Promote waiting jobs, then fill the next queued job (unless paused).

        Returns the id of the job it ran, or None when there was nothing to do.
        """
        if self.stopping.is_set() or not self._gate.try_enter():
            return None
        try:
            job_id, run_id = self._claim_next()
            if run_id is None:
                return job_id
            try:
                self.run_job(job_id, run_id)
            finally:
                self._gate.release_slot()
            return job_id
        finally:
            self._gate.leave()

    def _claim_next(self) -> tuple[str | None, str | None]:
        """Return (job id, run id) of the job to fill next, holding a run slot for it.

        A job whose filled window is still open goes straight back on it, with no run: then
        the run id is None. Both are None when there is nothing to do.
        """
        with self.store.tx() as db:
            queue = JobQueue(db, self.store.now())
            queue.promote_waiting()
            if db.state.get("paused"):
                return None, None
            job = queue.next_queued()
            if job is None:
                return None, None
            session = self.forms.get(job["id"])
            if session is not None and session.context is not None:
                self.outcomes.back_on_held_window(db, job, session)  # no second window
                return job["id"], None
            if not self._gate.try_take_slot():
                return None, None  # other users' runs fill the machine; it stays queued
            jobs.reset_progress(job)
            job["question"] = None
            job["internal"]["question"] = None
            return job["id"], self.claim(job)

    # ----- one run -----

    def run_job(self, job_id: str, run_id: str) -> str | None:
        """Fill one claimed job up to `needs_input`, `handoff` or `ready` (never submits).

        Returns the job's state afterwards, or None when the run no longer owned the job.
        """
        try:
            ctx = self.setup.prepare(job_id, run_id)
        except KeyError:
            return None
        except UnsupportedLink:
            return self._finish(job_id, run_id, self.outcomes.to_unsupported)
        except Exception as error:  # pylint: disable=broad-except  # shown on the job instead
            log.exception("Couldn't prepare job %s", job_id)
            return self._finish(job_id, run_id, lambda db, job: self.outcomes.to_failed(
                db, job, f"Couldn't start: {error}"))
        try:
            result = self.execute(ctx, submit=False)
        except Exception as error:  # pylint: disable=broad-except  # shown on the job instead
            log.exception("Run for job %s crashed", job_id)
            result = RunResult("failed", f"The agent crashed: {error}")
        session = ctx.session
        if session is not None and result.held is not None:
            # Held before the job shows `ready`, so a submit right away finds it. Kept even if
            # the job was cancelled or skipped meanwhile: applying again reuses the window.
            self.forms.hold(session)
            session.watching = result.status == "handoff"  # the person finishes it there
        return self._finish(job_id, run_id, lambda db, job: self.outcomes.apply_result(
            db, job, ctx, result))

    def _finish(self, job_id: str, run_id: str, apply) -> str | None:
        """Apply a run's outcome if the run still owns the job; return the job's state."""
        self.end_run(run_id)
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is None:
                return None
            if not owns(job, run_id):
                if job.get("state") == JobState.OPEN:  # cancelled mid-run: drop what it filled
                    jobs.reset_progress(job)
                return None
            apply(db, job)
            job["internal"]["runId"] = None
            job["internal"]["cancelRequested"] = False
            return job["state"]

    def execute(self, ctx: RunContext, submit: bool = False) -> RunResult:
        """Fill the form for `ctx` on a new FormSession thread (never pressing Submit).

        The session keeps the browser open if the fill ends `ready`; this thread only waits for
        the fill. `submit` is True for a submit that fills the form again first.
        """
        try:
            ctx.fields = ctx.form.read_fields()
        except Exception:  # pylint: disable=broad-except  # ApplyRun reads them again and says why
            ctx.fields = []
        run = self.setup.apply_run(
            ctx, on_event=lambda kind, **data: self.on_event(ctx, submit, kind, data),
            should_stop=lambda: self.should_stop(ctx))
        hooks = SessionHooks(on_confirmed=self._on_window_confirmed,
                             on_window_closed=self.outcomes.window_closed,
                             on_ended=self._events.browser_closed)
        self._active.add(ctx.run_id)
        try:
            ctx.session = FormSession(ctx.job_id, lambda: run.run(ctx.form, shot_name=ctx.job_id),
                                      context=ctx, hooks=hooks).start()
            return ctx.session.wait_filled()
        finally:
            self.end_run(ctx.run_id)

    # ----- ownership -----

    def should_stop(self, ctx: RunContext) -> bool:
        """Return True when the run must stop before its next field."""
        if self.is_aborted(ctx.run_id):
            return True
        with self.store.tx() as db:
            job = jobs.find(db, ctx.job_id)
            return job is None or not owns(job, ctx.run_id)

    def is_aborted(self, run_id: str) -> bool:
        """Return True when the worker is stopping or this run was cancelled."""
        return self.stopping.is_set() or run_id in self._cancelled

    def end_run(self, run_id: str) -> None:
        """Forget a run that is over."""
        self._active.discard(run_id)
        self._cancelled.discard(run_id)

    # ----- submits and events -----

    def submit_run(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Submit a claimed `ready` job on its held window, or fill it again first."""
        return self._submits.run(job_id, run_id)

    def on_event(self, ctx: RunContext, submit: bool, kind: str, data: dict) -> None:
        """Show one of the agent's run events on the job."""
        self._events.handle(ctx, submit, kind, data)

    def _on_window_confirmed(self, session: FormSession, result: RunResult) -> None:
        """On a session thread: a watched window shows the thank-you page, so record it."""
        if self.outcomes.window_confirmed(session, result):
            self.wake()
