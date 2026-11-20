"""AUTH_MODE=clerk: every request needs a Clerk session token, and each user has their own data.

The tests sign their own tokens with a throwaway RSA key (the app is given a verifier that
trusts it), and Clerk's Backend API is replaced by `FakeClerkUsers`. Nothing goes online.
"""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import create_app
from server.clerk import TokenVerifier, bearer_token, issuer_from_publishable_key
from server.config import load_config
from server.live_view import CLOSE_NO_BROWSER
from server.routes.live import CLOSE_UNAUTHENTICATED, LIVE_PROTOCOL
from server.tests.job_helpers import add_job, apply, upload_resume

ISSUER = "https://example-app.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"
ALICE, BOB = "user_alice123", "user_bob456"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(user_id: str = ALICE, *, key=KEY, issuer: str = ISSUER, azp: str | None = ORIGIN,
          expires_in: int = 60) -> str:
    now = int(time.time())
    claims = {"sub": user_id, "iss": issuer, "iat": now, "nbf": now - 5, "exp": now + expires_in,
              "sid": "sess_1"}
    if azp:
        claims["azp"] = azp
    return jwt.encode(claims, key, algorithm="RS256")


def as_user(user_id: str = ALICE) -> dict:
    return {"Authorization": f"Bearer {token(user_id)}"}


class FakeClerkUsers:
    """Stands in for server.clerk.ClerkUsers."""

    def __init__(self):
        self.deleted = []

    def identity(self, user_id: str) -> dict:
        first = user_id.split("_")[1].rstrip("0123456789").title()
        return {"firstName": first, "lastName": "Tester", "email": f"{first.lower()}@example.com"}

    def delete(self, user_id: str) -> bool:
        self.deleted.append(user_id)
        return True


@pytest.fixture
def make_clerk_app(data_dir, server_env):  # pylint: disable=unused-argument
    built_apps = []

    def build(**overrides):
        config = load_config(data_dir)
        config.auth_mode = "clerk"
        config.allowed_origins = (ORIGIN,)
        config.submit_real_form = False
        for name, value in overrides.items():
            setattr(config, name, value)
        built = create_app(config=config, start_worker=False, verifier=TokenVerifier(
            ISSUER, config.allowed_origins, key_for=lambda _token: KEY.public_key()))
        built.state.accounts.clerk_users = FakeClerkUsers()
        built_apps.append(built)
        return built
    yield build
    for built in built_apps:
        for account in built.state.accounts.all():
            account.worker.close_forms_for_tests()


@pytest.fixture
def clerk_app(make_clerk_app):  # pylint: disable=redefined-outer-name
    return make_clerk_app()


@pytest.fixture
def api(clerk_app):  # pylint: disable=redefined-outer-name
    with TestClient(clerk_app) as test_client:
        yield test_client


# ----- tokens -----

def test_publishable_key_names_the_issuer():
    # base64("example-app.clerk.accounts.dev$")
    key = "pk_test_ZXhhbXBsZS1hcHAuY2xlcmsuYWNjb3VudHMuZGV2JA"
    assert issuer_from_publishable_key(key) == ISSUER
    assert issuer_from_publishable_key("not-a-key") == ""
    assert issuer_from_publishable_key("pk_test_!!!") == ""


def test_bearer_token():
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("bearer  abc ") == "abc"
    assert bearer_token("Basic abc") is None
    assert bearer_token(None) is None


@pytest.mark.parametrize("path", ["/api/session", "/api/jobs", "/api/profile", "/api/answers",
                                  "/api/applications", "/api/settings", "/api/agent/status",
                                  "/api/account/export", "/api/screenshots/x.png"])
def test_every_route_needs_a_token(api, path):
    response = api.get(path)
    assert response.status_code == 401, path
    assert response.json()["code"] == "unauthenticated"


def test_health_needs_no_token(api):
    body = api.get("/api/health").json()
    assert body["ok"] is True and body["authMode"] == "clerk"


@pytest.mark.parametrize("bad", [
    lambda: token(key=OTHER_KEY),                       # signed by someone else
    lambda: token(issuer="https://evil.example"),       # another Clerk instance
    lambda: token(expires_in=-120),                     # expired
    lambda: token(azp="https://evil.example"),          # made for another site's page
    lambda: token("../../etc"),                         # not a user id
    lambda: "garbage",
])
def test_bad_tokens_are_refused(api, bad):
    response = api.get("/api/session", headers={"Authorization": f"Bearer {bad()}"})
    assert response.status_code == 401


def test_unsigned_tokens_are_refused(api):
    unsigned = jwt.encode({"sub": ALICE, "iss": ISSUER, "exp": int(time.time()) + 60}, None,
                          algorithm="none")
    assert api.get("/api/session",
                   headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_a_token_without_a_page_is_fine(api):
    """Tokens from scripts carry no `azp`."""
    headers = {"Authorization": f"Bearer {token(azp=None)}"}
    assert api.get("/api/session", headers=headers).status_code == 200


# ----- accounts -----

def test_first_request_creates_the_account_with_the_persons_identity(api, data_dir):
    body = api.get("/api/session", headers=as_user(ALICE)).json()
    assert body == {"user": {"id": ALICE, "name": "Alice Tester", "email": "alice@example.com"},
                    "profileConfirmed": False}
    profile = api.get("/api/profile", headers=as_user(ALICE)).json()
    assert (profile["firstName"], profile["email"]) == ("Alice", "alice@example.com")
    assert (data_dir / "users" / ALICE / "state.json").is_file()
    assert not (data_dir / "state.json").exists()  # nothing lands in the shared folder


def test_users_only_see_their_own_data(api, data_dir):
    upload_resume(_As(api, ALICE))
    saved = api.post("/api/answers", headers=as_user(ALICE), json={
        "category": "Logistics", "question": "Favourite colour?", "answer": "Green"})
    assert saved.status_code == 201, saved.text
    assert api.post("/api/profile/confirm", headers=as_user(ALICE)).status_code == 200
    job = add_job(_As(api, ALICE))

    assert api.get("/api/session", headers=as_user(BOB)).json()["profileConfirmed"] is False
    assert api.get("/api/answers", headers=as_user(BOB)).json() == []
    assert api.get("/api/jobs", headers=as_user(BOB)).json() == []
    assert api.get(f"/api/jobs/{job['id']}", headers=as_user(BOB)).status_code == 404
    assert api.get("/api/profile", headers=as_user(BOB)).json()["resume"] is None
    assert len(api.get("/api/answers", headers=as_user(ALICE)).json()) == 1
    assert [j["id"] for j in api.get("/api/jobs", headers=as_user(ALICE)).json()] == [job["id"]]
    assert (data_dir / "users" / ALICE / "answer_bank.json").is_file()
    assert not (data_dir / "users" / BOB / "answer_bank.json").exists()


def test_accounts_come_back_after_a_restart(api, make_clerk_app):
    api.get("/api/session", headers=as_user(ALICE))
    assert api.post("/api/profile/confirm", headers=as_user(ALICE)).status_code == 200
    again = make_clerk_app()
    assert [account.user_id for account in again.state.accounts.all()] == [ALICE]
    with TestClient(again) as client:
        assert client.get("/api/session", headers=as_user(ALICE)).json()["profileConfirmed"]


def test_local_sign_in_is_off(api):
    response = api.post("/api/auth/google", json={"returnTo": "/"})
    assert response.status_code == 400 and response.json()["code"] == "use_clerk"
    assert api.post("/api/auth/logout").status_code == 204


def test_delete_account_removes_only_that_user(api, clerk_app, data_dir):
    api.get("/api/session", headers=as_user(ALICE))
    api.get("/api/session", headers=as_user(BOB))
    assert api.delete("/api/account", headers=as_user(ALICE)).status_code == 204
    assert not (data_dir / "users" / ALICE).exists()
    assert (data_dir / "users" / BOB / "state.json").is_file()
    assert clerk_app.state.accounts.clerk_users.deleted == [ALICE]
    assert [account.user_id for account in clerk_app.state.accounts.all()] == [BOB]


# ----- the live view socket -----

def test_the_socket_needs_a_token(api):
    with api.websocket_connect("/api/jobs/j-1/live", subprotocols=[LIVE_PROTOCOL]) as socket:
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_UNAUTHENTICATED
    with api.websocket_connect("/api/jobs/j-1/live") as socket:
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_UNAUTHENTICATED


def test_the_socket_takes_the_token_as_a_subprotocol(api):
    with api.websocket_connect("/api/jobs/j-1/live",
                               subprotocols=[LIVE_PROTOCOL, token(ALICE)]) as socket:
        assert socket.accepted_subprotocol == LIVE_PROTOCOL
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_NO_BROWSER  # signed in; the job just has no browser


# ----- sharing the machine -----

def test_a_full_machine_leaves_the_job_queued(api, clerk_app):
    """All workers share the run slots: with none free, the job waits instead of opening a
    browser."""
    upload_resume(_As(api, ALICE))
    assert api.post("/api/profile/confirm", headers=as_user(ALICE)).status_code == 200
    job = add_job(_As(api, ALICE))
    apply(_As(api, ALICE), job["id"])
    alice = clerk_app.state.accounts.get(ALICE)
    bob = clerk_app.state.accounts.get(BOB)
    assert alice.worker._run_slots is bob.worker._run_slots  # pylint: disable=protected-access
    slots = alice.worker._run_slots  # pylint: disable=protected-access
    taken = 0
    while slots.acquire(blocking=False):  # pylint: disable=consider-using-with
        taken += 1
    try:
        assert taken == clerk_app.state.config.max_concurrent_runs
        assert alice.worker.run_next() is None
        state = api.get(f"/api/jobs/{job['id']}", headers=as_user(ALICE)).json()["state"]
        assert state == "queued"
    finally:
        for _ in range(taken):
            slots.release()


class _As:
    """A TestClient that sends one user's token with every request (for the job helpers)."""

    def __init__(self, client: TestClient, user_id: str):
        self._client, self._user_id = client, user_id

    def _call(self, method: str, url: str, **kwargs):
        headers = {**as_user(self._user_id), **kwargs.pop("headers", {})}
        return self._client.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._call("PUT", url, **kwargs)


