"""Local sign-in: /session, /auth/google and /auth/logout."""
from fastapi.testclient import TestClient


def test_first_visit_is_signed_out(client):
    """First visit is signed out."""
    response = client.get("/api/session")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_session_after_sign_in(signed_in):
    """After signing in, /session returns the user."""
    response = signed_in.get("/api/session")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "local"
    assert body["user"]["name"] and body["user"]["email"]
    assert body["profileConfirmed"] is False


def test_logout_then_401(signed_in):
    """After signing out, /session answers 401."""
    assert signed_in.post("/api/auth/logout").status_code == 204
    response = signed_in.get("/api/session")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthenticated"
    assert body["message"]


def test_google_sign_in_returns_callback_and_signs_in(signed_in):
    """Google sign in returns callback and signs in."""
    signed_in.post("/api/auth/logout")
    response = signed_in.post("/api/auth/google", json={"returnTo": "/inbox?tab=new"})
    assert response.status_code == 200
    url = response.json()["authorizationUrl"]
    assert url.startswith("/auth/callback")
    assert url == "/auth/callback?returnTo=/inbox%3Ftab%3Dnew"
    assert signed_in.get("/api/session").status_code == 200


def test_google_sign_in_without_body(client):
    """Signing in works without a request body."""
    response = client.post("/api/auth/google")
    assert response.status_code == 200
    assert response.json()["authorizationUrl"] == "/auth/callback?returnTo=/"


def test_signed_in_state_survives_restart(signed_in, make_app):  # pylint: disable=unused-argument  # signs in first
    """Signed in state survives restart."""
    with TestClient(make_app()) as again:
        assert again.get("/api/session").status_code == 200
        again.post("/api/auth/logout")
    with TestClient(make_app()) as third:
        assert third.get("/api/session").status_code == 401


def test_user_comes_from_profile(signed_in, app):
    """The session's user name comes from the profile; a blank email falls back."""
    with app.state.store.tx() as db:
        db.profile.update(firstName="Mary", middleName="Ann", lastName="Smith", email="")
    user = signed_in.get("/api/session").json()["user"]
    assert user == {"id": "local", "name": "Mary Ann Smith", "email": "demo@example.com"}
    with app.state.store.tx() as db:
        db.profile.update(middleName="")
    assert signed_in.get("/api/session").json()["user"]["name"] == "Mary Smith"
