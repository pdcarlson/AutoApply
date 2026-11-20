"""Sign-in route: /session."""
from fastapi import APIRouter, Depends

from server.accounts import Account, get_account
from server.names import full_name
from server.store import Db

router = APIRouter()


def current_user(db: Db, user_id: str) -> dict:
    """Return the User, derived from the profile on every call.

    What Clerk knows about the person (`state.user`) fills in for an empty profile.
    """
    profile = db.profile
    known = db.state.get("user") or {}
    return {
        "id": user_id,
        "name": full_name(profile) or known.get("name") or "",
        "email": (profile.get("email") or "").strip() or known.get("email") or "",
    }


def session_of(db: Db, user_id: str) -> dict:
    """Return the Session body (also returned by POST /profile/confirm)."""
    return {"user": current_user(db, user_id),
            "profileConfirmed": bool(db.state.get("profileConfirmed"))}


@router.get("/session")
def get_session(account: Account = Depends(get_account)):
    """Return the signed-in user's session."""
    with account.store.tx() as db:
        return session_of(db, account.user_id)
