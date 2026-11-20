"""Submit runs: presses Submit on a held window, or fills the form again first when it's gone."""
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from agent.runner.apply_run import RunResult
from server.runs.form_session import FormSession
from server.runs.run_context import SubmitOutcome
from server.runs.run_gate import RunGate

if TYPE_CHECKING:
    from server.runs.agent_worker import AgentWorker

log = logging.getLogger(__name__)

WINDOW_GONE_BEFORE_SUBMIT = "The new form window closed before Submit."


class SubmitRuns:  # pylint: disable=too-few-public-methods  # one entry point: run
    """Runs the browser part of POST /jobs/:id/submit for one worker, in the request's thread.

    It never overlaps another browser run of the worker, and never closes the window unless
    the confirmation was seen and saved. The caller applies the outcome to the job.
    """

    def __init__(self, worker: "AgentWorker", gate: RunGate):
        self.worker = worker
        self.gate = gate

    def run(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Submit a claimed `ready` job: on its held window, or after filling it again."""
        try:
            with self.gate.exclusive():
                try:
                    return self._submit(job_id, run_id)
                finally:
                    self.worker.end_run(run_id)
        finally:
            self.worker.wake()  # the loop held back while this ran

    def _submit(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Submit on the held window if it is still there, else fill the form again first."""
        session = self.worker.forms.get(job_id)
        if session is not None:
            outcome = self._submit_held(session, run_id)
            if outcome is not None:
                return outcome
            log.info("The held form for job %s is gone; filling it again", job_id)
        return self._submit_again(job_id, run_id)

    def _submit_held(self, session: FormSession, run_id: str) -> SubmitOutcome | None:
        """Press Submit on the held page; return None when the page is gone (nothing pressed)."""
        ctx = replace(session.context, run_id=run_id, pressed_submit=False, session=session)
        result = session.submit(
            on_event=lambda kind, **data: self.worker.on_event(ctx, True, kind, data),
            should_stop=lambda: self.worker.should_stop(ctx),
            should_abort=lambda: self.worker.is_aborted(run_id),
            confirm_timeout_s=self.worker.config.confirm_timeout_s)
        return None if result is None else SubmitOutcome(ctx, result)

    def _submit_again(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Fill the form again (held, on its own thread), then press Submit on it."""
        try:
            ctx = self.worker.setup.prepare(job_id, run_id)
        except KeyError:
            return SubmitOutcome(None, RunResult("cancelled", "The job is gone."), True)
        except Exception as error:  # pylint: disable=broad-except  # answered as a failed submit
            log.exception("Couldn't prepare the submit for job %s", job_id)
            return SubmitOutcome(None, RunResult("failed", f"Couldn't start: {error}"), True)
        try:
            result = self.worker.execute(ctx, submit=True)
        except Exception as error:  # pylint: disable=broad-except  # answered as a failed submit
            log.exception("Submit for job %s crashed", job_id)
            return SubmitOutcome(ctx, RunResult("failed", f"The agent crashed: {error}"), True)
        session = ctx.session
        if session is None or result.held is None:  # needs_input, failed or cancelled
            return SubmitOutcome(ctx, result, True)
        self.worker.forms.hold(session)
        if result.status == "handoff":  # a protected step: the person finishes it, not Submit
            session.watching = True
            return SubmitOutcome(ctx, result, True)
        outcome = self._submit_held(session, run_id)
        if outcome is None:
            outcome = SubmitOutcome(ctx, RunResult("failed", WINDOW_GONE_BEFORE_SUBMIT))
        outcome.refilled = True
        return outcome
