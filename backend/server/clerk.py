"""Clerk sign-in for AUTH_MODE=clerk: checking session tokens and looking users up.

The web app signs the person in with Clerk (Google) and sends Clerk's short-lived session token
with every request (`Authorization: Bearer <token>`). `TokenVerifier.verify` checks its
signature against Clerk's public keys, its issuer, its expiry and the page it was made for, and
returns the claims; `claims["sub"]` is the Clerk user id.

`ClerkUsers` talks to Clerk's Backend API with CLERK_SECRET_KEY: the person's name and email for
a new account, and deleting the Clerk user on DELETE /account. Without a secret key it does
nothing.
"""
import base64
import binascii
import logging
from dataclasses import dataclass
from typing import Callable

import httpx
import jwt

from server.errors import ApiError

log = logging.getLogger(__name__)

CLERK_API = "https://api.clerk.com/v1"
LEEWAY_SECONDS = 10
TIMEOUT_SECONDS = 10.0


def unauthenticated(message: str = "Sign in to continue.") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def issuer_from_publishable_key(key: str) -> str:
    """`pk_test_<base64 of "your-app.clerk.accounts.dev$">` -> `https://your-app.clerk.accounts.dev`.

    Returns "" when `key` isn't a Clerk publishable key.
    """
    parts = key.strip().split("_", 2)
    if len(parts) != 3 or parts[0] != "pk":
        return ""
    encoded = parts[2] + "=" * (-len(parts[2]) % 4)
    try:
        host = base64.urlsafe_b64decode(encoded).decode("ascii").rstrip("$")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""
    return f"https://{host}" if host and "/" not in host else ""


class TokenVerifier:
    """Checks Clerk session tokens. `key_for(token)` returns the public key that signed it;
    by default it comes from the issuer's JWKS (fetched once and cached)."""

    def __init__(self, issuer: str, allowed_origins: tuple[str, ...] = (),
                 key_for: Callable[[str], object] | None = None):
        if not issuer:
            raise ValueError("AUTH_MODE=clerk needs CLERK_PUBLISHABLE_KEY (or CLERK_ISSUER).")
        self.issuer = issuer.rstrip("/")
        self.allowed_origins = tuple(allowed_origins)
        if key_for is None:
            jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True,
                                   timeout=TIMEOUT_SECONDS)
            key_for = lambda token: jwks.get_signing_key_from_jwt(token).key  # noqa: E731
        self._key_for = key_for

    def verify(self, token: str | None) -> dict:
        """The token's claims. Raises ApiError 401 for a missing, expired or forged token."""
        if not token:
            raise unauthenticated()
        try:
            claims = jwt.decode(token, self._key_for(token), algorithms=["RS256"],
                                issuer=self.issuer, leeway=LEEWAY_SECONDS,
                                options={"require": ["exp", "sub", "iss"], "verify_aud": False})
        except jwt.PyJWKClientConnectionError:
            log.exception("Couldn't fetch Clerk's signing keys")
            raise ApiError(503, "auth_unavailable",
                           "Sign-in can't be checked right now. Try again in a moment.") from None
        except jwt.PyJWTError:
            raise unauthenticated() from None
        # `azp` is the origin of the page the token was issued to. A token minted for another
        # site's page (same Clerk instance) is refused.
        page = (claims.get("azp") or "").rstrip("/")
        if page and self.allowed_origins and page not in self.allowed_origins:
            raise unauthenticated()
        return claims


def bearer_token(header: str | None) -> str | None:
    """The token of an `Authorization: Bearer <token>` header."""
    scheme, _, token = (header or "").partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


@dataclass
class ClerkUsers:
    """Clerk's Backend API for one instance. Every call is best effort."""

    secret_key: str = ""

    def _request(self, method: str, user_id: str) -> dict | None:
        if not self.secret_key:
            return None
        try:
            response = httpx.request(method, f"{CLERK_API}/users/{user_id}",
                                     headers={"Authorization": f"Bearer {self.secret_key}"},
                                     timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("Clerk %s for user %s failed", method, user_id, exc_info=True)
            return None

    def identity(self, user_id: str) -> dict:
        """{"firstName", "lastName", "email"} for a user; empty strings for what isn't known."""
        user = self._request("GET", user_id) or {}
        emails = user.get("email_addresses") or []
        primary = next((e for e in emails if e.get("id") == user.get("primary_email_address_id")),
                       emails[0] if emails else {})
        return {"firstName": (user.get("first_name") or "").strip(),
                "lastName": (user.get("last_name") or "").strip(),
                "email": (primary.get("email_address") or "").strip()}

    def delete(self, user_id: str) -> bool:
        """Deletes the Clerk user (their sign-in). True when Clerk confirmed it."""
        return self._request("DELETE", user_id) is not None
