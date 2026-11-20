"""What a form session does to its held window: press Submit, type a code, note a confirmation."""
import logging
from collections.abc import Callable

from agent.runner.apply_run import HeldForm, RunResult

log = logging.getLogger(__name__)


class HeldWindowActions:
    """Acts on one job's held window, on its session thread; a crash becomes a failed result."""

    def __init__(self, job_id: str, is_closing: Callable[[], bool]):
        self.job_id = job_id
        self._is_closing = is_closing

    def submit(self, held: HeldForm, kwargs: dict) -> RunResult:
        """Press Submit on the held window and wait for the confirmation."""
        should_abort = self._abort_check(kwargs)
        try:
            return held.submit(should_abort=should_abort, **kwargs)
        except Exception as error:  # pylint: disable=broad-except  # reported as a failed submit
            log.exception("Submitting job %s crashed", self.job_id)
            return RunResult("failed", f"The agent crashed: {error}")

    def enter_code(self, held: HeldForm, kwargs: dict) -> RunResult:
        """Type the emailed code into the watched window and wait for the confirmation."""
        code = kwargs.pop("code")
        should_abort = self._abort_check(kwargs)
        try:
            return held.enter_code(code, should_abort=should_abort, **kwargs)
        except Exception as error:  # pylint: disable=broad-except  # reported as a failed submit
            log.exception("Entering the code for job %s crashed", self.job_id)
            return RunResult("failed", f"The agent crashed: {error}", pressed=True,
                             asked_for_code=True)

    @staticmethod
    def confirmed_now(held: HeldForm, last_result: RunResult | None) -> RunResult:
        """Return the result for a watched window that now shows the thank-you page."""
        before = last_result or held.filled
        result = RunResult("submitted", "The site confirmed the application.",
                           filled=list(before.filled), filled_detail=list(before.filled_detail),
                           filled_screenshot=before.filled_screenshot, pressed=True)
        held.save_screenshot(result)
        return result

    def _abort_check(self, kwargs: dict) -> Callable[[], bool]:
        """Return a should_abort that also stops when the session is closing."""
        abort = kwargs.pop("should_abort", None)
        return lambda: self._is_closing() or bool(abort and abort())
