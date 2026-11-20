"""Auth: /session, /auth/google, /auth/logout (spec 2.13).

AUTH_MODE=local (the demo): there is no Google and no cookie. "Begin Onboarding" flips
`state.signedIn`, which is persisted in state.json; the user starts signed out. Only /session
checks it.

AUTH_MODE=clerk: the web app signs in with Clerk and every request carries its session token
(server.accounts checks it), so /session answers for whoever the token names, /auth/logout has
nothing to forget, and /auth/google isn't used.
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from server.accounts import Account, get_account
from server.errors import ApiError
from server.names import full_name
from server.store import DEMO_USER, Db, get_store

router = APIRouter()


class GoogleSignInBody(BaseModel):
    returnTo: str | None = None


def current_user(db: Db, user_id: str = DEMO_USER["id"]) -> dict:
    """The User, derived from the profile on every call. What sign-in knows about the person
    (`state.user`, set for Clerk accounts) fills in for an empty profile."""
    profile = db.profile
    known = db.state.get("user") or DEMO_USER
    return {
        "id": user_id,
        "name": full_name(profile) or known.get("name") or "",
        "email": (profile.get("email") or "").strip() or known.get("email") or "",
    }


def session_of(db: Db, user_id: str = DEMO_USER["id"]) -> dict:
    """The Session body (also returned by POST /profile/confirm)."""
    return {"user": current_user(db, user_id),
            "profileConfirmed": bool(db.state.get("profileConfirmed"))}


def _multi_user(request: Request) -> bool:
    return request.app.state.accounts.multi_user


@router.get("/session")
def get_session(request: Request, account: Account = Depends(get_account)):
    with account.store.tx() as db:
        if not _multi_user(request) and not db.state.get("signedIn"):
            raise ApiError(401, "unauthenticated", "Sign in to continue.")
        return session_of(db, account.user_id)


@router.post("/auth/google")
def start_google_sign_in(request: Request, body: GoogleSignInBody | None = None):
    if _multi_user(request):
        raise ApiError(400, "use_clerk", "Sign in with Google on the sign-in page.")
    return_to = (body.returnTo if body else None) or "/"
    with get_store(request).tx() as db:
        db.state["signedIn"] = True
    return {"authorizationUrl": "/auth/callback?returnTo=" + quote(return_to, safe="/")}


@router.post("/auth/logout", status_code=204)
def sign_out(request: Request):
    if not _multi_user(request):
        with get_store(request).tx() as db:
            db.state["signedIn"] = False
    return Response(status_code=204)
