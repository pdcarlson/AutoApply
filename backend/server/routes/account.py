"""Account routes: GET /account/export and DELETE /account."""
import json
import logging

from fastapi import APIRouter, Depends, Request, Response

from server.store import Store, get_store

log = logging.getLogger(__name__)

router = APIRouter()

EXPORT_FILENAME = "auto-apply-export.json"


def _public(record):
    """Drops server-only keys: anything starting with "_" and the jobs' `internal` blob."""
    if not isinstance(record, dict):
        return record
    return {k: v for k, v in record.items() if not k.startswith("_") and k != "internal"}


@router.get("/account/export")
def export_account(request: Request, store: Store = Depends(get_store)):
    bank = request.app.state.answer_bank
    with store.tx() as db:
        data = {
            "exportedAt": store.now_iso(),
            "profile": _public(db.profile),
            "commonAnswers": db.common_answers,
            "preferences": db.preferences,
            "settings": db.settings,
            "answers": bank.list() if bank is not None else [],
            "applications": [
                {k: v for k, v in _public(app).items() if k != "screenshotUrl"}
                for app in db.applications
            ],
            "jobs": [_public(job) for job in db.jobs],
        }
        body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        content=body.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"'},
    )


@router.delete("/account", status_code=204)
def delete_account(request: Request, store: Store = Depends(get_store)):
    """Deletes everything in the data dir but .gitignore and signs the user out.

    The current run, if any, is told to stop; its job is gone once the wipe is done. Filled
    form windows are left open (the software never closes one before it is submitted); they
    are no longer tied to any job, and the person closes them.
    """
    worker = request.app.state.worker
    worker.cancel_current()
    store.wipe()
    worker.wake()
    log.info("Account data deleted")
    return Response(status_code=204)
