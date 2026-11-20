"""One job's browser on its own thread: fills the form, then holds the filled window open."""
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from agent.runner.apply_run import HeldForm, RunResult
from server.runs.held_window_actions import HeldWindowActions

log = logging.getLogger(__name__)

CLOSE_WAIT_SECONDS = 15.0
REPLY_POLL_SECONDS = 1.0
WATCH_SECONDS = 1.0  # how often a held window is checked (closed by the person? confirmed?)
GONE = "The browser stopped responding while submitting."
ENDED = "The form session has ended."


class _Command(StrEnum):
    """What other threads can ask the session thread to do with the held window."""

    SUBMIT = "submit"  # press Submit and wait for the confirmation
    CODE = "code"  # type the code the site emailed into a watched window
    CALL = "call"  # run a function on the held form (screenshots, tests)
    CLOSE = "close"  # close the browser and end the thread


@dataclass
class SessionHooks:
    """What a FormSession tells its owner. Each is called on the session thread."""

    on_confirmed: Callable | None = None  # (session, result): a watched window was confirmed
    on_window_closed: Callable | None = None  # (session): the person closed a held window
    on_ended: Callable | None = None  # (session): the thread is done and its browser closed


class FormSession:  # pylint: disable=too-many-instance-attributes  # state shared across threads
    """Fills one job's form on its own thread, then keeps the filled window open and serves it.

    Playwright's sync API only works on the thread that launched the browser, so the browser
    never leaves this thread: other threads send it commands. The window is closed only once
    the application was submitted and a screenshot of that saved, or when the person closes it.
    """

    def __init__(self, job_id: str, fill: Callable[[], RunResult], context=None,
                 hooks: SessionHooks | None = None):
        self.job_id = job_id
        self.context = context  # whatever the owner wants to keep with the session
        self.result: RunResult | None = None  # the fill's result
        self.watching = False  # Submit pressed (or a protected step left), no confirmation yet
        self.pressed = False  # Submit was pressed on this window at some point
        self.submit_result: RunResult | None = None  # the last submit's result
        self._fill = fill
        self._hooks = hooks or SessionHooks()
        self._commands: queue.Queue = queue.Queue()
        self._filled = threading.Event()
        self._closing = threading.Event()
        self._actions = HeldWindowActions(job_id, self._closing.is_set)
        self._ended = threading.Event()  # the window is closed (or about to be): no more commands
        self._thread = threading.Thread(target=self._main, name=f"form-{job_id}", daemon=True)

    # ----- from any thread -----

    def start(self) -> "FormSession":
        """Start the fill on the session thread; return the session."""
        self._thread.start()
        return self

    def wait_filled(self) -> RunResult:
        """Block until the fill ends; return its result."""
        self._filled.wait()
        return self.result

    @property
    def alive(self) -> bool:
        """Return True while the thread runs (filling, or holding the filled form)."""
        return self._thread.is_alive() and not self._ended.is_set()

    def submit(self, **kwargs) -> RunResult | None:
        """Press Submit on the held page (HeldForm.submit kwargs) and wait for the confirmation.

        The window stays open unless it was confirmed and its screenshot saved. Returns None,
        without pressing anything, when the window is gone, so the caller can fill it again.
        """
        if not self.alive or self._closing.is_set():
            return None
        return self._send(_Command.SUBMIT, kwargs, RunResult("failed", GONE))

    def enter_code(self, code: str, **kwargs) -> RunResult | None:
        """Type `code` into the watched window and wait for the confirmation, or return None."""
        if not self.alive or self._closing.is_set():
            return None
        return self._send(_Command.CODE, {**kwargs, "code": code}, None)

    def call(self, function: Callable[[HeldForm], object]):
        """Run function(held_form) on the session thread and return what it returns."""
        if not self.alive:
            raise RuntimeError(ENDED)
        is_ok, value = self._send(_Command.CALL, function, (False, RuntimeError(ENDED)))
        if not is_ok:
            raise value
        return value

    def close(self, wait: bool = True) -> None:
        """Close the browser and end the thread.

        Only for a window whose screenshot was just saved (mark-submitted), and for tests.
        """
        self._closing.set()
        self._commands.put((_Command.CLOSE, None, None))
        if wait:
            self.join()

    def join(self) -> None:
        """Wait (a while) for the session thread to end."""
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(CLOSE_WAIT_SECONDS)
            if self._thread.is_alive():
                log.warning("The browser for job %s didn't close in time", self.job_id)

    def _send(self, command: _Command, argument, if_gone):
        """Queue a command for the session thread and wait for its reply (`if_gone` if none)."""
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put((command, argument, reply))
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
        """Fill, hold, and tell the owner when it's all over."""
        try:
            self._fill_and_hold()
        finally:
            self._notify(self._hooks.on_ended)

    def _fill_and_hold(self) -> None:
        """Run the fill; if it left the browser open, serve the held window until it closes."""
        try:
            self.result = self._fill()
        except Exception as error:  # pylint: disable=broad-except  # reported as a failed run
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
        except Exception:  # pylint: disable=broad-except  # the window must outlive any bug here
            # Leave the window as it is: the browser goes away with the process, not before.
            log.exception("The held form for job %s stopped being watched", self.job_id)
            self._idle_until_closed(held)
        finally:
            held.close()
            self._ended.set()

    def _serve(self, held: HeldForm) -> None:
        """Serve commands and watch the window; return once it may be closed."""
        while True:
            try:
                command, argument, reply = self._commands.get(timeout=WATCH_SECONDS)
            except queue.Empty:
                command = None
            if command is _Command.CLOSE:
                return
            if command is _Command.CALL:
                try:
                    reply.put((True, argument(held)))
                except Exception as error:  # pylint: disable=broad-except  # raised in the caller
                    reply.put((False, error))
            elif command in (_Command.SUBMIT, _Command.CODE):
                if self._run_send(held, command, dict(argument), reply):
                    return
            elif self._check_window(held):
                return

    def _check_window(self, held: HeldForm) -> bool:
        """Between commands: notice a closed or confirmed window. True when it may be closed."""
        if not held.window_open():
            self._notify(self._hooks.on_window_closed)
            return True
        if self.watching and not self._closing.is_set() and held.confirmed():
            result = self._actions.confirmed_now(held, self.submit_result)
            self._notify(self._hooks.on_confirmed, result)
            self.watching = False
            # Without a saved screenshot the window stays open until the person closes it.
            return result.screenshot == str(held.result_shot)
        return False

    def _run_send(self, held: HeldForm, command: _Command, kwargs: dict,
                  reply: queue.Queue) -> bool:
        """Run a submit or code command and reply. True when the window may be closed.

        A code is only typed into a watched window, so the job is told when that one is gone
        (a submit's caller fills the form again instead).
        """
        if not held.window_open():
            reply.put(None)  # the person closed it
            if command is _Command.CODE:
                self._notify(self._hooks.on_window_closed)
            return True
        if command is _Command.SUBMIT:
            result = self._actions.submit(held, kwargs)
            self.pressed = self.pressed or result.pressed
        else:
            result = self._actions.enter_code(held, kwargs)
        self.submit_result = result
        is_done = result.window_closed or (result.status == "submitted"
                                           and result.screenshot == str(held.result_shot))
        if is_done:
            held.close()  # confirmed and saved (or already gone): before the reply
            self._ended.set()
        reply.put(result)
        if is_done:
            if result.window_closed and command is _Command.CODE:
                self._notify(self._hooks.on_window_closed)
            return True
        self.watching = result.pressed and result.status != "submitted"
        return False

    def _idle_until_closed(self, held: HeldForm) -> None:
        """After an error: keep the window until the person closes it or `close()` is called."""
        while True:
            try:
                command, _argument, reply = self._commands.get(timeout=WATCH_SECONDS)
            except queue.Empty:
                command = None
            if command is _Command.CLOSE:
                return
            if command is not None and reply is not None:
                reply.put(None if command is _Command.SUBMIT
                          else (False, RuntimeError("unavailable")))
            try:
                if not held.window_open():
                    return
            except Exception:  # pylint: disable=broad-except  # a broken browser counts as closed
                return

    def _notify(self, callback: Callable | None, *args) -> None:
        """Call one of the owner's hooks; a hook that fails is logged, not raised."""
        if callback is None:
            return
        try:
            callback(self, *args)
        except Exception:  # pylint: disable=broad-except  # the hook's bug mustn't end the session
            log.exception("Handling the held form for job %s failed", self.job_id)
