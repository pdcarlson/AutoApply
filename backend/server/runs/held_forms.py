"""The filled form windows a worker holds open for review, by job id."""
import threading

from server.runs.form_session import FormSession


class HeldForms:
    """The worker's live form sessions by job id. Thread-safe.

    It never closes a window by itself, and there is no cap: skip, cancel, applying again and
    deleting the account all leave the window open, and applying to the job again reuses it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, FormSession] = {}
        self._detached: list[FormSession] = []  # replaced by a newer session for the same job

    def __len__(self) -> int:
        """Return how many jobs have a live session."""
        return len(self.job_ids())

    def job_ids(self) -> list[str]:
        """Return the ids of the jobs with a live session, oldest first."""
        with self._lock:
            self._prune()
            return list(self._sessions)

    def get(self, job_id: str) -> FormSession | None:
        """Return the live session holding the job's window, or None."""
        with self._lock:
            session = self._sessions.get(job_id)
            if session is not None and not session.alive:
                del self._sessions[job_id]
                return None
            return session

    def hold(self, session: FormSession) -> None:
        """Keep `session` for its job. One already there stays open, just detached."""
        with self._lock:
            self._prune()
            old = self._sessions.get(session.job_id)
            if old is not None and old is not session:
                self._detached.append(old)
            self._sessions[session.job_id] = session

    def close_all(self) -> None:
        """Close every window and wait for the threads (test teardown, or a deleted account)."""
        with self._lock:
            sessions = list(self._sessions.values()) + self._detached
            self._sessions.clear()
            self._detached.clear()
        for session in sessions:
            session.close(wait=False)
        for session in sessions:
            session.join()

    def _prune(self) -> None:
        """Forget sessions whose thread has ended."""
        self._sessions = {job_id: session for job_id, session in self._sessions.items()
                          if session.alive}
        self._detached = [session for session in self._detached if session.alive]
