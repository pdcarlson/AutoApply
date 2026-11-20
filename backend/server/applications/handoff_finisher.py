"""Finishes `handoff` jobs: a code the site emailed, typed in, or the person marking it sent."""
from pathlib import Path

from server import jobs
# records is imported as a module: it imports the routes package, which imports this file.
from server.applications import reasons, records
from server.errors import ApiError, not_found
from server.jobs import EventKind, JobState
from server.store import Db, Store

NOT_HANDOFF = "This job isn’t waiting for you to finish it."
NO_CODE = "Enter the code from the email."
NO_CODE_WINDOW = ("This job isn’t waiting for an emailed code anymore. Check the site, and mark "
                  "it submitted if it went through.")


class HandoffFinisher:
    """Finishes jobs that wait for the person, through the window the worker still holds."""

    def __init__(self, store: Store, worker):
        self.store = store
        self.worker = worker

    def enter_code(self, job_id: str, code) -> dict:
        """Type the emailed code into the job's watched window, send it; return the Application.

        Not taken: 422 code_rejected, and the job stays in `handoff`, still asking. This
        doesn't wait for other browser runs (the code can expire meanwhile): the window is
        driven on its own thread.
        """
        code = "".join(str(code or "").split())
        if not code:
            raise ApiError(422, "invalid_code", NO_CODE)
        with self.store.tx() as db:
            existing = records.recorded_for(db, job_id)
            if existing is not None:  # its window recorded it a moment ago
                return records.to_summary(existing, self.store.now())
            if not jobs.asks_for_code(self._handoff_job(db, job_id)):
                raise ApiError(409, "no_code_window", NO_CODE_WINDOW)
        session = self.worker.held_form(job_id)
        result = session.enter_code(code) if session is not None and session.watching else None
        with self.store.tx() as db:
            existing = records.recorded_for(db, job_id)
            if existing is not None:
                return records.to_summary(existing, self.store.now())
            job = jobs.find(db, job_id)
            if job is None:
                raise not_found("Job")
            if result is not None and result.status == "submitted":  # sent, whatever happened
                record = records.ApplicationRecorder(self.store, db).record_confirmed(job, result)
                return records.to_summary(record, self.store.now())
            error = self._code_not_taken(job, result)
        raise error

    def mark_submitted(self, job_id: str) -> dict:
        """Record a `handoff` job the person finished on the site; return the Application.

        A window still open for the job is screenshotted first (the application's screenshot),
        and only once that is saved and the application recorded is the window closed.
        """
        with self.store.tx() as db:
            existing = records.recorded_for(db, job_id)
            if existing is not None:  # its window recorded it a moment ago
                return records.to_summary(existing, self.store.now())
            self._handoff_job(db, job_id)
        session = self.worker.held_form(job_id)
        shot, is_confirmed = None, False
        if session is not None:
            try:
                shot, is_confirmed = session.call(_final_look)
            except Exception:  # pylint: disable=broad-except  # any failure means the window closed
                session = None  # nothing to screenshot or close
        with self.store.tx() as db:
            record = records.recorded_for(db, job_id) or self._record_finished(
                db, job_id, session, Path(shot).name if shot else None, is_confirmed)
            summary = records.to_summary(record, self.store.now())
        if session is not None and shot is not None:
            session.close()  # submitted, and the screenshot is saved
        return summary

    def _record_finished(self, db: Db, job_id: str, session, shot_name: str | None,
                         is_confirmed: bool) -> dict:
        """Record the application the person finished: confirmed, if the agent saw it sent."""
        job = self._handoff_job(db, job_id)
        recorder = records.ApplicationRecorder(self.store, db)
        if is_confirmed and session is not None and session.pressed:
            return recorder.record_confirmed(job, session.submit_result, screenshot=shot_name)
        now = self.store.now_iso()
        return recorder.record(job, submitted_by=records.SubmittedBy.YOU, at=now, events=[
            {"kind": EventKind.ACCENT,
             "text": f"You finished it on {job.get('company', '')}’s site", "at": now},
            {"kind": EventKind.CURRENT, "text": records.WAITING, "at": now},
        ], screenshot=recorder.screenshot(shot_name))

    def _handoff_job(self, db: Db, job_id: str) -> dict:
        """Return the job if it is in `handoff`, or raise 409 not_handoff."""
        job = jobs.find(db, job_id)
        if job is None or job.get("state") != JobState.HANDOFF:
            raise ApiError(409, "not_handoff", NOT_HANDOFF)
        return job

    def _code_not_taken(self, job: dict, result) -> ApiError:
        """Update a job whose code didn't confirm it; return the error to answer with."""
        now = self.store.now_iso()
        if result is not None and result.asked_for_code and not result.window_closed:
            jobs.add_event(job, EventKind.AMBER,
                           f"{job.get('ats') or 'The site'} didn’t take the code you entered", now)
            return ApiError(422, "code_rejected", result.reason)
        # The window is gone (its close handler already said so), or it stopped asking.
        is_closed = result is not None and result.window_closed
        if job.get("state") == JobState.HANDOFF:
            job["internal"]["askedForCode"] = False
            if not is_closed:
                job["reason"] = NO_CODE_WINDOW
                jobs.add_event(job, EventKind.AMBER, NO_CODE_WINDOW, now)
        return ApiError(409, "no_code_window",
                        reasons.WINDOW_CLOSED if is_closed else NO_CODE_WINDOW)


def _final_look(held) -> tuple[str | None, bool]:
    """On the session thread: return (saved screenshot path or None, shows the thank-you page)."""
    is_confirmed = held.confirmed()
    return (str(held.result_shot) if held.save_screenshot() else None), is_confirmed
