"""Auth for the single local user: /session, /auth/google, /auth/logout (spec 2.13).

There is no Google and no cookie. "Begin Onboarding" flips `state.signedIn`, which is
persisted in state.json; the user starts signed out. Only /session checks it.
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from server.errors import ApiError
from server.names import full_name
from server.store import DEMO_USER, Db, Store, get_store

router = APIRouter()


class GoogleSignInBody(BaseModel):
    returnTo: str | None = None


def current_user(db: Db) -> dict:
    """The User, derived from the profile on every call."""
    profile = db.profile
    return {
        "id": DEMO_USER["id"],
        "name": full_name(profile) or DEMO_USER["name"],
        "email": (profile.get("email") or "").strip() or DEMO_USER["email"],
    }


def session_of(db: Db) -> dict:
    """The Session body (also returned by POST /profile/confirm)."""
    return {"user": current_user(db), "profileConfirmed": bool(db.state.get("profileConfirmed"))}


@router.get("/session")
def get_session(store: Store = Depends(get_store)):
    with store.tx() as db:
        if not db.state.get("signedIn"):
            raise ApiError(401, "unauthenticated", "Sign in to continue.")
        return session_of(db)


@router.post("/auth/google")
def start_google_sign_in(body: GoogleSignInBody | None = None, store: Store = Depends(get_store)):
    return_to = (body.returnTo if body else None) or "/"
    with store.tx() as db:
        db.state["signedIn"] = True
    return {"authorizationUrl": "/auth/callback?returnTo=" + quote(return_to, safe="/")}


@router.post("/auth/logout", status_code=204)
def sign_out(store: Store = Depends(get_store)):
    with store.tx() as db:
        db.state["signedIn"] = False
    return Response(status_code=204)
