"""Filled forms kept open in their browser for the review, so Submit doesn't fill them again.

Playwright's sync API is thread-bound: a browser can only be used from the thread that launched
it. So every fill runs on its own `FormSession` thread. The fill ends like any run; when it ends
`ready` (with ApplyRun(hold=True)) the browser stays open and the thread waits for one command:

    submit  press Submit on the filled page, wait for the confirmation, close, reply
    close   close the browser and end the thread

`HeldForms` is the registry the worker keeps them in, by job id, oldest first and capped
(`HELD_FORMS_MAX`, default 5): holding one more closes the oldest, whose job then falls back to
filling the form again at submit time. Closed on cancel, skip, apply, DELETE /account, after
a submit, when the job is no longer `ready`, and on shutdown.
"""
import logging
import queue
import threading
from collections import OrderedDict
from collections.abc import Callable

from agent.runner.apply_run import RunResult

log = logging.getLogger(__name__)

CLOSE_WAIT_SECONDS = 15.0
REPLY_POLL_SECONDS = 1.0
GONE = "The browser stopped responding while submitting."


class FormSession:  # pylint: disable=too-many-instance-attributes
    """One job's browser on its own thread: fills the form, then holds it until submit or close.

    `fill()` runs on the session thread and returns the RunResult; a `ready` result with `held`
    keeps the browser open. `context` is whatever the caller wants to keep with it.
    """

    def __init__(self, job_id: str, fill: Callable[[], RunResult], context=None):
        self.job_id = job_id
        self.context = context
        self._fill = fill
        self._commands: queue.Queue = queue.Queue()
        self._filled = threading.Event()
        self._closing = threading.Event()
        self.result: RunResult | None = None
        self._thread = threading.Thread(target=self._main, name=f"form-{job_id}", daemon=True)

    # ----- from any thread -----

    def start(self) -> "FormSession":
        self._thread.start()
        return self

    def wait_filled(self) -> RunResult:
        """Blocks until the fill ends; returns its result."""
        self._filled.wait()
        return self.result

    @property
    def alive(self) -> bool:
        """True while the thread runs (filling, or holding the filled form)."""
        return self._thread.is_alive()

    def submit(self, **kwargs) -> RunResult | None:
        """Presses Submit on the held page (HeldForm.submit kwargs) and closes the browser.

        Blocks until done. Returns None, without pressing anything, when the page is gone
        (closed, crashed, or the session was closed), so the caller can fill it again.
        """
        if not self.alive or self._closing.is_set():
            return None
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(("submit", kwargs, reply))
        return self._wait(reply, RunResult("failed", GONE))

    def call(self, function: Callable):
        """Runs function(held_form) on the session thread and returns what it returns."""
        if not self.alive:
            raise RuntimeError("The form session has ended.")
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(("call", function, reply))
        ok, value = self._wait(reply, (False, RuntimeError("The form session has ended.")))
        if not ok:
            raise value
        return value

    def close(self, wait: bool = True) -> None:
        """Closes the browser and ends the thread (a submit in progress stops waiting)."""
        self._closing.set()
        self._commands.put(("close", None, None))
        if wait:
            self.join()

    def join(self) -> None:
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(CLOSE_WAIT_SECONDS)
            if self._thread.is_alive():
                log.warning("The browser for job %s didn't close in time", self.job_id)

    def _wait(self, reply: queue.Queue, if_gone):
        while True:
            try:
                return reply.get(timeout=REPLY_POLL_SECONDS)
            except queue.Empty:
                if not self._thread.is_alive():
                    try:
                        return reply.get_nowait()
                    except queue.Empty:
                        return if_gone

    # ----- on the session thread -----

    def _main(self) -> None:
        try:
            self.result = self._fill()
        except Exception as error:  # pylint: disable=broad-except
            log.exception("The fill for job %s crashed", self.job_id)
            self.result = RunResult("failed", f"The agent crashed: {error}")
        finally:
            self._filled.set()
        held = self.result.held
        if held is None:  # the run already closed its browser
            return
        try:
            self._serve(held)
        finally:
            held.close()

    def _serve(self, held) -> None:
        while True:
            command, argument, reply = self._commands.get()
            if command == "close":
                return
            if command == "call":
                try:
                    reply.put((True, argument(held)))
                except Exception as error:  # pylint: disable=broad-except
                    reply.put((False, error))
                continue
            # submit: one shot, then the thread ends
            if self._closing.is_set() or not held.usable():
                held.close()
                reply.put(None)
                return
            reply.put(self._submit(held, dict(argument)))
            return

    def _submit(self, held, kwargs: dict) -> RunResult:
        abort = kwargs.pop("should_abort", None)
        try:
            return held.submit(should_abort=lambda: self._closing.is_set()
                               or bool(abort and abort()), **kwargs)
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Submitting job %s crashed", self.job_id)
            return RunResult("failed", f"The agent crashed: {error}")
        finally:
            held.close()


class HeldForms:
    """The worker's filled forms waiting for review, by job id, oldest first. Thread-safe."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, FormSession] = OrderedDict()

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def job_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions)

    def get(self, job_id: str) -> FormSession | None:
        with self._lock:
            return self._sessions.get(job_id)

    def hold(self, session: FormSession, limit: int) -> None:
        """Keeps `session`; closes one held earlier for the same job and the oldest past `limit`."""
        with self._lock:
            replaced = self._sessions.pop(session.job_id, None)
            self._sessions[session.job_id] = session
            evicted = []
            while len(self._sessions) > max(limit, 0):
                evicted.append(self._sessions.popitem(last=False)[1])
        for old in (replaced, *evicted):
            if old is not None:
                log.info("Closing the held form for job %s (over the limit of %d)",
                         old.job_id, limit)
                old.close()

    def take(self, job_id: str) -> FormSession | None:
        """Removes and returns the held form for `job_id` (to submit it), if any."""
        with self._lock:
            return self._sessions.pop(job_id, None)

    def discard(self, session: FormSession) -> None:
        """Forgets `session` if it's still the one held for its job, and closes it."""
        with self._lock:
            if self._sessions.get(session.job_id) is session:
                del self._sessions[session.job_id]
        session.close()

    def close(self, job_id: str) -> None:
        session = self.take(job_id)
        if session is not None:
            session.close()

    def close_all(self) -> None:
        """Closes every held form (shutdown, DELETE /account); waits for their threads."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close(wait=False)
        for session in sessions:
            session.join()
