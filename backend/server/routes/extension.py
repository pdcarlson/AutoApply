"""Routes for the browser extension (extension/ at the repo root), which fills a job's form in
the person's own browser: GET /extension/plan, GET /extension/jobs/:id/resume and
POST /extension/jobs/:id/submitted. See server.browser_fill.
"""
import mimetypes

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from server import browser_fill
from server.config import Config, get_config
from server.store import Store, get_store

router = APIRouter()


@router.get("/extension/plan")
def get_plan(url: str, request: Request, store: Store = Depends(get_store),
             config: Config = Depends(get_config)):
    return browser_fill.plan(store, request.app.state.answer_bank, config, url)


@router.get("/extension/jobs/{job_id}/resume")
def get_resume(job_id: str, request: Request, store: Store = Depends(get_store)):
    path = browser_fill.resume_file(store, request.app.state.answer_bank, job_id)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/extension/jobs/{job_id}/submitted")
def mark_submitted_in_browser(job_id: str, request: Request,
                              store: Store = Depends(get_store)):
    try:
        return browser_fill.submitted(store, request.app.state.worker, job_id)
    finally:
        request.app.state.worker.wake()
