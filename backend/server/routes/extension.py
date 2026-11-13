"""Routes for filling a job's form in the person's own browser (extension/ at the repo root),
either with the Chrome extension or, in any browser, with the "Fill with AutoApply" bookmark:
GET /extension/plan, GET /extension/jobs/:id/resume, POST /extension/jobs/:id/submitted, and for
the bookmark GET /extension/fill-window (its small window) and GET /extension/fill.js.
See server.browser_fill.
"""
import mimetypes

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from server.config import BACKEND_DIR

from server import browser_fill
from server.config import Config, get_config
from server.store import Store, get_store

router = APIRouter()

FILL_DIR = BACKEND_DIR.parent / "extension"  # one copy of the fill script for both ways


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


@router.get("/extension/fill-window")
def get_fill_window():
    """The small window the bookmark opens: it hands the answers to the job page."""
    return FileResponse(FILL_DIR / "fill-window.html", media_type="text/html")


@router.get("/extension/fill.js")
def get_fill_script():
    """The script the job page runs to fill its own form (the extension's fill.js)."""
    return FileResponse(FILL_DIR / "fill.js", media_type="text/javascript")
