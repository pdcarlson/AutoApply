"""Sign-in routes: /session, /auth/google and /auth/logout."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from server.accounts import Account, get_account
from server.errors import ApiError
from server.names import full_name
from server.store import Db, get_store
from server.store_docs import DEMO_USER

router = APIRouter()


class GoogleSignInBody(BaseModel):
    """Where to go back to after signing in."""

    returnTo: str | None = None


def current_user(db: Db, user_id: str = DEMO_USER["id"]) -> dict:
    """Return the User, derived from the profile on every call.

    What sign-in knows about the person (`state.user`, set for Clerk accounts) fills in for an
    empty profile.
    """
    profile = db.profile
    known = db.state.get("user") or DEMO_USER
    return {
        "id": user_id,
        "name": full_name(profile) or known.get("name") or "",
        "email": (profile.get("email") or "").strip() or known.get("email") or "",
    }


def session_of(db: Db, user_id: str = DEMO_USER["id"]) -> dict:
    """Return the Session body (also returned by POST /profile/confirm)."""
    return {"user": current_user(db, user_id),
            "profileConfirmed": bool(db.state.get("profileConfirmed"))}


def _multi_user(request: Request) -> bool:
    """Return True with real sign-in (AUTH_MODE=clerk)."""
    return request.app.state.accounts.multi_user


@router.get("/session")
def get_session(request: Request, account: Account = Depends(get_account)):
    """Return the session; in local mode, 401 until "Begin Onboarding" has signed in."""
    with account.store.tx() as db:
        if not _multi_user(request) and not db.state.get("signedIn"):
            raise ApiError(401, "unauthenticated", "Sign in to continue.")
        return session_of(db, account.user_id)


@router.post("/auth/google")
def start_google_sign_in(request: Request, body: GoogleSignInBody | None = None):
    """Sign the local user in (local mode has no real Google sign-in)."""
    if _multi_user(request):
        raise ApiError(400, "use_clerk", "Sign in with Google on the sign-in page.")
    return_to = (body.returnTo if body else None) or "/"
    with get_store(request).tx() as db:
        db.state["signedIn"] = True
    return {"authorizationUrl": "/auth/callback?returnTo=" + quote(return_to, safe="/")}


@router.post("/auth/logout", status_code=204)
def sign_out(request: Request):
    """Sign the local user out; with Clerk the web app signs out and nothing is kept here."""
    if not _multi_user(request):
        with get_store(request).tx() as db:
            db.state["signedIn"] = False
    return Response(status_code=204)
