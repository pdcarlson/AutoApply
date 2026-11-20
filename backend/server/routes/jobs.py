"""Inbox routes: list, add, apply, cancel, skip and restore jobs."""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from server import jobs
from server.accounts import get_bank, get_worker
from server.config import Config, get_config
from server.errors import ApiError, not_found
from server.job_intake import JobIntake
from server.job_queue import JobQueue
from server.jobs import JobState
from server.store import Store, get_store

router = APIRouter()


class AddJobBody(BaseModel):
    """The body of POST /jobs."""

    url: str


class JobIdsBody(BaseModel):
    """A body that lists job ids."""

    jobIds: list[str]


@router.get("/jobs")
def list_jobs(store: Store = Depends(get_store)):
    """Return every job in the Inbox."""
    with store.tx() as db:
        return [jobs.to_api_job(job) for job in db.jobs if jobs.visible(job)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, store: Store = Depends(get_store)):
    """Return one Inbox job with its fields."""
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or not jobs.visible(job):
            raise not_found("Job")
        return jobs.to_api_job_detail(job)


@router.post("/jobs", status_code=201)
def add_job(body: AddJobBody, request: Request, store: Store = Depends(get_store),
            config: Config = Depends(get_config)):
    """Add a pasted job link to the Inbox."""
    return jobs.to_api_job(JobIntake(store, get_bank(request), config).add(body.url))


@router.post("/jobs/apply")
def apply_jobs(body: JobIdsBody, request: Request, store: Store = Depends(get_store)):
    """Queue open jobs for the agent, up to the daily limit; the rest wait."""
    with store.tx() as db:
        if not db.state.get("profileConfirmed"):
            raise ApiError(409, "profile_not_confirmed", "Confirm your profile before applying.")
        queued, deferred = JobQueue(db, store.now()).apply(body.jobIds)
    get_worker(request).wake()  # a job whose window is still open reuses it
    return {"queued": queued, "deferred": deferred}


@router.post("/jobs/cancel", status_code=204)
def cancel_jobs(body: JobIdsBody, request: Request, store: Store = Depends(get_store)):
    """Send queued, running or waiting jobs back to `open`."""
    with store.tx() as db:
        # A filled window stays open; applying again reuses it.
        JobQueue(db, store.now()).cancel(body.jobIds)
    get_worker(request).wake()
    return Response(status_code=204)


@router.post("/jobs/{job_id}/skip", status_code=204)
def skip_job(job_id: str, request: Request, store: Store = Depends(get_store)):
    """Hide a job from the Inbox (it can be restored)."""
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or not jobs.visible(job):
            raise not_found("Job")
        jobs.skip(db, job)  # a filled window stays open (only the person closes it)
    get_worker(request).wake()
    return Response(status_code=204)


@router.post("/jobs/{job_id}/restore")
def restore_job(job_id: str, store: Store = Depends(get_store)):
    """Bring a skipped job back to the Inbox as `open`."""
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or job.get("state") != JobState.SKIPPED:
            raise not_found("Job")
        jobs.restore(job)
        return jobs.to_api_job(job)
