"""Application routes: submitting, finishing a handoff, and listing and updating applications."""
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server.accounts import get_worker
from server.applications import records
from server.applications.handoff_finisher import HandoffFinisher
from server.applications.submitter import Submitter
from server.config import Config, get_config
from server.errors import not_found
from server.store import Store, get_store

router = APIRouter()


@router.post("/jobs/{job_id}/submit")
def submit_job(job_id: str, request: Request, store: Store = Depends(get_store),
               config: Config = Depends(get_config)):
    """Submit a `ready` job; answers once the submit is done (the Review modal waits on it)."""
    try:
        return Submitter(store, get_worker(request), config).submit(job_id)
    finally:
        get_worker(request).wake()  # a freed place in today's limit, or the lock released


@router.post("/jobs/{job_id}/verification-code")
def enter_verification_code(job_id: str, request: Request, body: Any = Body(None),
                            store: Store = Depends(get_store)):
    """Type the code the site emailed into the job's open window and send it."""
    code = body.get("code") if isinstance(body, dict) else None
    return HandoffFinisher(store, get_worker(request)).enter_code(job_id, code)


@router.post("/jobs/{job_id}/mark-submitted")
def mark_submitted(job_id: str, request: Request, store: Store = Depends(get_store)):
    """Record a `handoff` job the person finished on the site."""
    return HandoffFinisher(store, get_worker(request)).mark_submitted(job_id)


@router.get("/applications")
def list_applications(store: Store = Depends(get_store)):
    """Return every application, newest first."""
    with store.tx() as db:
        now = store.now()
        return [records.to_summary(record, now) for record in records.newest_first(db)]


@router.get("/applications/{app_id}")
def get_application(app_id: str, store: Store = Depends(get_store)):
    """Return one application with its fields, timeline and screenshot."""
    with store.tx() as db:
        record = records.find(db, app_id)
        if record is None:
            raise not_found("Application")
        return records.to_detail(record, store.now())


@router.patch("/applications/{app_id}")
def patch_application(app_id: str, body: Any = Body(None), store: Store = Depends(get_store)):
    """Change an application's status."""
    status = body.get("status") if isinstance(body, dict) else None
    with store.tx() as db:
        record = records.find(db, app_id)
        if record is None:
            raise not_found("Application")
        records.set_status(record, status, store.now_iso())
        return records.to_summary(record, store.now())
