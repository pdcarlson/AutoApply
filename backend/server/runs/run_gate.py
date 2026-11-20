"""Lets one browser run at a time go per worker, within the runs the machine allows at once."""
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class RunGate:
    """One worker's run lock, plus the run slots every user's worker shares.

    The worker's loop only takes the gate when it is free. A submit (POST /jobs/:id/submit)
    waits for it, and while it waits the loop starts nothing new, so a long queue can't keep
    the submit waiting.
    """

    def __init__(self, slots: threading.Semaphore):
        self.slots = slots
        self._lock = threading.Lock()
        self._submits_waiting = 0
        self._waiting_guard = threading.Lock()

    def try_enter(self) -> bool:
        """Take the run lock for the loop, unless a submit waits for it or a run holds it."""
        if self._submits_waiting:
            return False
        return self._lock.acquire(blocking=False)  # pylint: disable=consider-using-with  # released by leave()

    def leave(self) -> None:
        """Give back the run lock taken by try_enter."""
        self._lock.release()

    def try_take_slot(self) -> bool:
        """Take one of the machine's run slots if one is free."""
        return self.slots.acquire(blocking=False)  # pylint: disable=consider-using-with  # released by release_slot()

    def release_slot(self) -> None:
        """Give back a run slot."""
        self.slots.release()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Hold the run lock and a slot for a run outside the loop, waiting for both."""
        with self._waiting_guard:
            self._submits_waiting += 1
        try:
            self._lock.acquire()  # pylint: disable=consider-using-with  # released below
        finally:
            with self._waiting_guard:
                self._submits_waiting -= 1
        self.slots.acquire()  # pylint: disable=consider-using-with  # released below
        try:
            yield
        finally:
            self.slots.release()
            self._lock.release()
