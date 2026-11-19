"""Sign-in: /session, /auth/google, /auth/google/callback, /auth/logout (spec 2.13).

With GOOGLE_OAUTH_CLIENT_ID set, sign-in goes through Google and the user is kept in the
session cookie. Without it, "Begin Onboarding" flips `state.signedIn` in state.json, which is
what the tests and the offline demo use.
"""
import secrets
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from server.config import Config, get_config
from server.errors import ApiError
from server.names import full_name
from server.store import DEMO_USER, Db, Store, get_store

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleSignInBody(BaseModel):
    returnTo: str | None = None


def _google_on(request: Request) -> bool:
    return bool(request.app.state.config.google_client_id)


def _signed_in(db: Db, request: Request) -> bool:
    if _google_on(request):
        return "user" in request.session
    return bool(db.state.get("signedIn"))


def current_user(db: Db, request: Request) -> dict:
    """The Google user when signed in with Google, otherwise derived from the profile."""
    if _google_on(request) and "user" in request.session:
        return request.session["user"]
    profile = db.profile
    return {
        "id": DEMO_USER["id"],
        "name": full_name(profile) or DEMO_USER["name"],
        "email": (profile.get("email") or "").strip() or DEMO_USER["email"],
    }


def session_of(db: Db, request: Request) -> dict:
    """The Session body (also returned by POST /profile/confirm)."""
    return {"user": current_user(db, request),
            "profileConfirmed": bool(db.state.get("profileConfirmed"))}


def _callback_url(**params: str) -> RedirectResponse:
    return RedirectResponse("/auth/callback?" + urlencode(params, safe="/"))


@router.get("/session")
def get_session(request: Request, store: Store = Depends(get_store)):
    with store.tx() as db:
        if not _signed_in(db, request):
            raise ApiError(401, "unauthenticated", "Sign in to continue.")
        return session_of(db, request)


@router.post("/auth/google")
def start_google_sign_in(request: Request, body: GoogleSignInBody | None = None,
                         store: Store = Depends(get_store),
                         config: Config = Depends(get_config)):
    return_to = (body.returnTo if body else None) or "/"
    if not _google_on(request):
        with store.tx() as db:
            db.state["signedIn"] = True
        return {"authorizationUrl": "/auth/callback?returnTo=" + quote(return_to, safe="/")}

    # Checked in the callback so the sign-in can only finish in the browser that started it
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["return_to"] = return_to
    params = {
        "client_id": config.google_client_id,
        "redirect_uri": config.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return {"authorizationUrl": GOOGLE_AUTH_URL + "?" + urlencode(params)}


@router.get("/auth/google/callback")
def finish_google_sign_in(request: Request, code: str = "", state: str = "", error: str = "",
                          config: Config = Depends(get_config)):
    expected = request.session.pop("oauth_state", None)
    return_to = request.session.pop("return_to", "/")
    if error:
        return _callback_url(error=error)
    if not code or not expected or not secrets.compare_digest(state, expected):
        return _callback_url(error="invalid_state")

    try:
        token = httpx.post(GOOGLE_TOKEN_URL, timeout=10, data={
            "code": code,
            "client_id": config.google_client_id,
            "client_secret": config.google_client_secret,
            "redirect_uri": config.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        token.raise_for_status()
        info = httpx.get(GOOGLE_USERINFO_URL, timeout=10, headers={
            "Authorization": "Bearer " + token.json()["access_token"]})
        info.raise_for_status()
        user = info.json()
        request.session["user"] = {
            "id": user["sub"],
            "name": user.get("name") or user.get("email", ""),
            "email": user.get("email", ""),
        }
    except (httpx.HTTPError, KeyError, ValueError):
        return _callback_url(error="failed")
    return _callback_url(returnTo=return_to)


@router.post("/auth/logout", status_code=204)
def sign_out(request: Request, store: Store = Depends(get_store)):
    request.session.clear()
    with store.tx() as db:
        db.state["signedIn"] = False
    return Response(status_code=204)
