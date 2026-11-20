"""The run queue and the daily limit: which jobs the agent works on next, and how many today."""
from datetime import datetime

from server import jobs
from server.jobs import EventKind, JobState
from server.store import Db, iso, parse_iso

# States that hold a place against the daily limit.
COMMITTED_STATES = (JobState.QUEUED, JobState.RUNNING, JobState.NEEDS_INPUT, JobState.READY)
CANCELLABLE_STATES = (JobState.QUEUED, JobState.RUNNING, JobState.WAITING)


class JobQueue:
    """The queue and the daily limit, read and changed through the `db` of an open tx.

    `state.queue` holds the ids of queued jobs in run order. A job stays in it while it runs
    and leaves it when the run ends.
    """

    def __init__(self, db: Db, now: datetime):
        self.db = db
        self.now = now

    def sent_today(self) -> int:
        """Return how many applications the agent sent today (local time), dry runs included."""
        today = self.now.astimezone().date()
        count = 0
        for application in self.db.applications:
            if application.get("submittedBy") != "agent":
                continue
            moment = parse_iso(application.get("submittedAt"))
            if moment and moment.astimezone().date() == today:
                count += 1
        return count

    def room(self) -> int:
        """Return how many more jobs can be queued today."""
        committed = self.sent_today() + sum(1 for job in self.db.jobs
                                            if job.get("state") in COMMITTED_STATES)
        return max(0, int(self.db.settings["dailyLimit"]) - committed)

    def order(self) -> list[str]:
        """Return running ids, then queued ids in run order, then waiting ids by approval."""
        by_id = {job.get("id"): job for job in self.db.jobs}
        running = [job["id"] for job in self.db.jobs if job.get("state") == JobState.RUNNING]
        queued = [job_id for job_id in self.db.state.get("queue", [])
                  if by_id.get(job_id, {}).get("state") == JobState.QUEUED]
        return running + queued + [job["id"] for job in self._waiting()]

    def status(self) -> dict:
        """Return the API `AgentStatus`."""
        return {
            "paused": bool(self.db.state.get("paused")),
            "sentToday": self.sent_today(),
            "dailyLimit": self.db.settings["dailyLimit"],
            "queue": self.order(),
        }

    def next_queued(self) -> dict | None:
        """Return the first job in `state.queue` that is still `queued`, or None."""
        for job_id in self.db.state.get("queue", []):
            job = jobs.find(self.db, job_id)
            if job is not None and job.get("state") == JobState.QUEUED:
                return job
        return None

    def apply(self, job_ids: list[str]) -> tuple[list[str], list[str]]:
        """Queue the first `room` open jobs and make the rest wait; return (queued, deferred).

        Ids that aren't `open` (or don't exist) are ignored.
        """
        free = self.room()
        at = iso(self.now)
        queued, deferred = [], []
        for job_id in dict.fromkeys(job_ids):
            job = jobs.find(self.db, job_id)
            if job is None or job.get("state") != JobState.OPEN:
                continue
            job["approvedAt"] = at
            jobs.add_event(job, EventKind.MUTED, "You pressed Apply", at)
            if len(queued) < free:
                job["state"] = JobState.QUEUED
                jobs.append_to_queue(self.db, job_id)
                queued.append(job_id)
            else:
                job["state"] = JobState.WAITING
                deferred.append(job_id)
        return queued, deferred

    def promote_waiting(self) -> list[str]:
        """Queue the oldest `waiting` jobs while the daily limit has room; return their ids."""
        promoted = []
        free = self.room()
        for job in self._waiting()[:free]:
            job["state"] = JobState.QUEUED
            jobs.append_to_queue(self.db, job["id"])
            promoted.append(job["id"])
        return promoted

    def cancel(self, job_ids: list[str]) -> list[str]:
        """Send queued, running or waiting jobs back to `open`; return their ids.

        A running job is detached from its run and is `open` right away; the worker stops
        between fields and leaves it alone.
        """
        cancelled = []
        for job_id in job_ids:
            job = jobs.find(self.db, job_id)
            if job is None or job.get("state") not in CANCELLABLE_STATES:
                continue
            jobs.to_open(job, clear_cache=True)
            jobs.remove_from_queue(self.db, job_id)
            cancelled.append(job_id)
        return cancelled

    def _waiting(self) -> list[dict]:
        """Return the `waiting` jobs, oldest approval first."""
        return sorted((job for job in self.db.jobs if job.get("state") == JobState.WAITING),
                      key=lambda job: job.get("approvedAt") or "")
