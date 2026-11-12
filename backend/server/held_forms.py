"""Filled forms kept open in their browser, so Submit doesn't fill them again.

The rule: the software never closes a filled-out form window unless the application was
submitted and a screenshot of that was saved. The only closes are:

- a confirmed submit, once `-result.png` is saved (right after Submit, or later while watching);
- POST /jobs/:id/mark-submitted, once the window's screenshot is saved (server.applications);
- the person closing the window themselves (noticed here, then the thread ends);
- the server process exiting (Chromium is its child), and tests' explicit teardown.

Playwright's sync API is thread-bound: a browser can only be used from the thread that launched
it. So every fill runs on its own `FormSession` thread. The fill ends like any run; when it ends
`ready` (ApplyRun(hold=True)) the browser stays open and the thread serves commands:

    submit  press Submit on the filled page and wait up to the timeout for the confirmation.
            Confirmed: save the screenshot, close, end. Pressed but not confirmed: reply, then
            keep the window open and *watch* it (every WATCH_SECONDS, no time limit) until the
            thank-you page shows up (then `on_confirmed`, screenshot, close) or the person
            closes the window (`on_window_closed`).
    call    run a function on the held form (screenshots for mark-submitted, tests)
    close   close the browser and end the thread (only after a saved screenshot, or in tests)

Between commands the thread checks every WATCH_SECONDS whether the person closed the window.

`HeldForms` is the worker's registry of live sessions by job id. There is no cap, and nothing in
a job's lifecycle (skip, cancel, apply again, DELETE /account) closes one: the window stays, and
applying to the job again reuses it.
"""
import logging
import queue
import threading
from collections.abc import Callable

from agent.runner.apply_run import RunResult

log = logging.getLogger(__name__)

CLOSE_WAIT_SECONDS = 15.0
REPLY_POLL_SECONDS = 1.0
WATCH_SECONDS = 1.0  # how often a held window is checked (closed by the person? confirmed?)
GONE = "The browser stopped responding while submitting."


class FormSession:  # pylint: disable=too-many-instance-attributes
    """One job's browser on its own thread: fills the form, then holds it (see the module doc).

    `fill()` runs on the session thread and returns the RunResult; a `ready` result with `held`
    keeps the browser open. `context` is whatever the caller wants to keep with it.
    `on_confirmed(session, result)` is called (on the session thread) when a watched window
    shows the thank-you page and its screenshot is saved; `on_window_closed(session)` when the
    person closes a held window. Exceptions they raise are logged.
    """

    def __init__(self, job_id: str, fill: Callable[[], RunResult], context=None,  # pylint: disable=too-many-arguments
                 on_confirmed: Callable | None = None,
                 on_window_closed: Callable | None = None):
        self.job_id = job_id
        self.context = context
        self._fill = fill
        self._on_confirmed = on_confirmed
        self._on_window_closed = on_window_closed
        self._commands: queue.Queue = queue.Queue()
        self._filled = threading.Event()
        self._closing = threading.Event()
        self._ended = threading.Event()  # the window is closed (or about to be): no more commands
        self.result: RunResult | None = None
        self.watching = False  # Submit was pressed, no confirmation yet: watching for it
        self.pressed = False  # Submit was pressed on this window at some point
        self.submit_result: RunResult | None = None  # the last submit's result
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
        return self._thread.is_alive() and not self._ended.is_set()

    def submit(self, **kwargs) -> RunResult | None:
        """Presses Submit on the held page (HeldForm.submit kwargs) and waits for the confirmation.

        Blocks until the confirmation shows up or the timeout runs out; the window stays open
        unless it was confirmed (and its screenshot saved). Returns None, without pressing
        anything, when the window is gone, so the caller can fill the form again.
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
        """Closes the browser and ends the thread.

        Only for a window whose screenshot was just saved (mark-submitted), and for tests.
        """
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
            self._ended.set()
            return
        try:
            self._serve(held)
        except Exception:  # pylint: disable=broad-except
            # Leave the window as it is: the browser goes away with the process, not before.
            log.exception("The held form for job %s stopped being watched", self.job_id)
            self._idle_until_closed(held)
        finally:
            held.close()
            self._ended.set()

    def _serve(self, held) -> None:
        """Serves commands and watches the window; returns when it may be closed."""
        while True:
            try:
                command, argument, reply = self._commands.get(timeout=WATCH_SECONDS)
            except queue.Empty:
                command = None
            if command == "close":
                return
            if command == "call":
                try:
                    reply.put((True, argument(held)))
                except Exception as error:  # pylint: disable=broad-except
                    reply.put((False, error))
                continue
            if command == "submit":
                if not held.window_open():
                    reply.put(None)  # the person closed it: the caller fills it again
                    return
                result = self._submit(held, dict(argument))
                self.submit_result = result
                done = result.window_closed or (result.status == "submitted"
                                                and result.screenshot == str(held.result_shot))
                if done:
                    held.close()  # confirmed and saved (or already gone): before the reply
                    self._ended.set()
                reply.put(result)
                if done:
                    return
                self.watching = result.pressed and result.status != "submitted"
                continue
            if not held.window_open():
                self._notify(self._on_window_closed)
                return
            if self.watching and not self._closing.is_set() and held.confirmed():
                result = self._confirmed_now(held)
                self._notify(self._on_confirmed, result)
                self.watching = False
                if result.screenshot == str(held.result_shot):
                    return
                # No screenshot, so the window stays open until the person closes it.

    def _idle_until_closed(self, held) -> None:
        """After an error: keep the window until the person closes it or `close()` is called."""
        while True:
            try:
                command, _argument, reply = self._commands.get(timeout=WATCH_SECONDS)
            except queue.Empty:
                command = None
            if command == "close":
                return
            if command is not None and reply is not None:
                reply.put(None if command == "submit" else (False, RuntimeError("unavailable")))
            try:
                if not held.window_open():
                    return
            except Exception:  # pylint: disable=broad-except
                return

    def _submit(self, held, kwargs: dict) -> RunResult:
        abort = kwargs.pop("should_abort", None)
        try:
            result = held.submit(should_abort=lambda: self._closing.is_set()
                                 or bool(abort and abort()), **kwargs)
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Submitting job %s crashed", self.job_id)
            result = RunResult("failed", f"The agent crashed: {error}")
        self.pressed = self.pressed or result.pressed
        return result

    def _confirmed_now(self, held) -> RunResult:
        """The RunResult for a watched window that now shows the thank-you page."""
        before = self.submit_result or held.filled
        result = RunResult("submitted", "The site confirmed the application.",
                           filled=list(before.filled), filled_detail=list(before.filled_detail),
                           filled_screenshot=before.filled_screenshot, pressed=True)
        held.save_screenshot(result)
        return result

    def _notify(self, callback, *args) -> None:
        if callback is None:
            return
        try:
            callback(self, *args)
        except Exception:  # pylint: disable=broad-except
            log.exception("Handling the held form for job %s failed", self.job_id)


class HeldForms:
    """The worker's live form sessions by job id. Thread-safe. Never closes one by itself."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, FormSession] = {}
        self._detached: list[FormSession] = []  # replaced by a newer session for the same job

    def __len__(self) -> int:
        return len(self.job_ids())

    def _prune(self) -> None:
        self._sessions = {job_id: s for job_id, s in self._sessions.items() if s.alive}
        self._detached = [s for s in self._detached if s.alive]

    def job_ids(self) -> list[str]:
        with self._lock:
            self._prune()
            return list(self._sessions)

    def get(self, job_id: str) -> FormSession | None:
        """The live session holding `job_id`'s window, if any."""
        with self._lock:
            session = self._sessions.get(job_id)
            if session is not None and not session.alive:
                del self._sessions[job_id]
                return None
            return session

    def hold(self, session: FormSession) -> None:
        """Keeps `session` for its job. One already there stays open, just detached."""
        with self._lock:
            self._prune()
            old = self._sessions.get(session.job_id)
            if old is not None and old is not session:
                self._detached.append(old)
            self._sessions[session.job_id] = session

    def close_all_for_tests(self) -> None:
        """Test teardown only: closes every window and waits for the threads."""
        with self._lock:
            sessions = list(self._sessions.values()) + self._detached
            self._sessions.clear()
            self._detached.clear()
        for session in sessions:
            session.close(wait=False)
        for session in sessions:
            session.join()
