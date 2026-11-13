"""Application routes (spec 2.11): POST /jobs/:id/submit, POST /jobs/:id/verification-code,
POST /jobs/:id/mark-submitted, GET /applications, GET /applications/:id and
PATCH /applications/:id.

POST /jobs/:id/submit answers once the submit is done (the Review modal waits on it). With
SUBMIT_REAL_FORM on it runs the browser in this request's thread, after any fill in progress.
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server import applications
from server.config import Config, get_config
from server.errors import not_found
from server.store import Store, get_store

router = APIRouter()


@router.post("/jobs/{job_id}/submit")
def submit_job(job_id: str, request: Request, store: Store = Depends(get_store),
               config: Config = Depends(get_config)):
    try:
        return applications.submit(store, request.app.state.worker, config, job_id)
    finally:
        request.app.state.worker.wake()  # a freed place in today's limit, or the lock released


@router.post("/jobs/{job_id}/verification-code")
def enter_verification_code(job_id: str, request: Request, body: Any = Body(None),
                            store: Store = Depends(get_store)):
    code = body.get("code") if isinstance(body, dict) else None
    return applications.enter_code(store, request.app.state.worker, job_id, code)


@router.post("/jobs/{job_id}/mark-submitted")
def mark_submitted(job_id: str, request: Request, store: Store = Depends(get_store)):
    return applications.mark_submitted(store, request.app.state.worker, job_id)


@router.get("/applications")
def list_applications(store: Store = Depends(get_store)):
    with store.tx() as db:
        now = store.now()
        return [applications.to_summary(r, now) for r in applications.newest_first(db)]


@router.get("/applications/{app_id}")
def get_application(app_id: str, store: Store = Depends(get_store)):
    with store.tx() as db:
        record = applications.find(db, app_id)
        if record is None:
            raise not_found("Application")
        return applications.to_detail(record, store.now())


@router.patch("/applications/{app_id}")
def patch_application(app_id: str, body: Any = Body(None), store: Store = Depends(get_store)):
    status = body.get("status") if isinstance(body, dict) else None
    with store.tx() as db:
        record = applications.find(db, app_id)
        if record is None:
            raise not_found("Application")
        applications.set_status(record, status, store.now_iso())
        return applications.to_summary(record, store.now())
