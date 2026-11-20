"""Account routes: GET /account/export and DELETE /account."""
import json
import logging

from fastapi import APIRouter, Depends, Request, Response

from server.accounts import get_account, get_bank
from server.store import Store, get_store

log = logging.getLogger(__name__)

router = APIRouter()

EXPORT_FILENAME = "auto-apply-export.json"


def _public(record):
    """Return the record without server-only keys: "_"-prefixed ones and jobs' `internal`."""
    if not isinstance(record, dict):
        return record
    return {k: v for k, v in record.items() if not k.startswith("_") and k != "internal"}


@router.get("/account/export")
def export_account(request: Request, store: Store = Depends(get_store)):
    """Return everything the person has saved, as a JSON file to download."""
    bank = get_bank(request)
    with store.tx() as db:
        data = {
            "exportedAt": store.now_iso(),
            "profile": _public(db.profile),
            "commonAnswers": db.common_answers,
            "preferences": db.preferences,
            "settings": db.settings,
            "answers": bank.list(),
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
def delete_account(request: Request):
    """Delete the whole account: its folder, its browsers and the Clerk user.

    The current run, if any, is told to stop. The browsers go too, as nobody else could close
    them on a server.
    """
    account = get_account(request)
    account.worker.cancel_current()
    account.store.wipe()  # drops the current run's result: its job is gone
    request.app.state.accounts.forget(account.user_id)
    log.info("Account data deleted")
    return Response(status_code=204)
