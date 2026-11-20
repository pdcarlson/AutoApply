"""Fake Clerk sign-in for tests: tokens signed with a throwaway key, and a fake Clerk API."""
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from server.clerk import TokenVerifier

ISSUER = "https://example-app.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"
ALICE, BOB = "user_alice123", "user_bob456"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(user_id: str = ALICE, *, key=KEY, issuer: str = ISSUER, azp: str | None = ORIGIN,
          expires_in: int = 3600) -> str:
    """Return a Clerk-style session token signed with the test key."""
    now = int(time.time())
    claims = {"sub": user_id, "iss": issuer, "iat": now, "nbf": now - 5, "exp": now + expires_in,
              "sid": "sess_1"}
    if azp:
        claims["azp"] = azp
    return jwt.encode(claims, key, algorithm="RS256")


def as_user(user_id: str = ALICE) -> dict:
    """Return the Authorization header for a user."""
    return {"Authorization": f"Bearer {token(user_id)}"}


def fake_verifier(allowed_origins: tuple[str, ...] = (ORIGIN,)) -> TokenVerifier:
    """Return a TokenVerifier that trusts the test key."""
    return TokenVerifier(ISSUER, allowed_origins, key_for=lambda _token: KEY.public_key())


def signed_in_client(app, user_id: str = ALICE) -> TestClient:
    """Return a TestClient that sends the user's token with every request."""
    return TestClient(app, headers=as_user(user_id))


class FakeClerkUsers:
    """Stands in for server.clerk.ClerkUsers."""

    def __init__(self):
        self.deleted = []

    def identity(self, user_id: str) -> dict:
        """Return the name and email Clerk would have for the user."""
        first = user_id.split("_")[1].rstrip("0123456789").title()
        return {"firstName": first, "lastName": "Tester", "email": f"{first.lower()}@example.com"}

    def delete(self, user_id: str) -> bool:
        """Record the deleted user and say Clerk confirmed it."""
        self.deleted.append(user_id)
        return True
