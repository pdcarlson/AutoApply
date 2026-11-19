from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient


def test_first_visit_is_signed_out(client):
    response = client.get("/api/session")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_session_after_sign_in(signed_in):
    response = signed_in.get("/api/session")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "local"
    assert body["user"]["name"] and body["user"]["email"]
    assert body["profileConfirmed"] is False


def test_logout_then_401(signed_in):
    assert signed_in.post("/api/auth/logout").status_code == 204
    response = signed_in.get("/api/session")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthenticated"
    assert body["message"]


def test_google_sign_in_returns_callback_and_signs_in(signed_in):
    signed_in.post("/api/auth/logout")
    response = signed_in.post("/api/auth/google", json={"returnTo": "/inbox?tab=new"})
    assert response.status_code == 200
    url = response.json()["authorizationUrl"]
    assert url.startswith("/auth/callback")
    assert url == "/auth/callback?returnTo=/inbox%3Ftab%3Dnew"
    assert signed_in.get("/api/session").status_code == 200


def test_google_sign_in_without_body(client):
    response = client.post("/api/auth/google")
    assert response.status_code == 200
    assert response.json()["authorizationUrl"] == "/auth/callback?returnTo=/"


def test_signed_in_state_survives_restart(signed_in, make_app):  # pylint: disable=unused-argument
    with TestClient(make_app()) as again:
        assert again.get("/api/session").status_code == 200
        again.post("/api/auth/logout")
    with TestClient(make_app()) as third:
        assert third.get("/api/session").status_code == 401


def test_user_comes_from_profile(signed_in, app):
    with app.state.store.tx() as db:
        db.profile.update(firstName="Mary", middleName="Ann", lastName="Smith", email="")
    user = signed_in.get("/api/session").json()["user"]
    assert user == {"id": "local", "name": "Mary Ann Smith", "email": "demo@example.com"}
    with app.state.store.tx() as db:
        db.profile.update(middleName="")
    assert signed_in.get("/api/session").json()["user"]["name"] == "Mary Smith"


def _start_google_sign_in(client, return_to="/"):
    url = client.post("/api/auth/google", json={"returnTo": return_to}).json()["authorizationUrl"]
    return parse_qs(urlparse(url).query)


def _fake_google(monkeypatch):
    def fake_post(url, **_kwargs):
        return httpx.Response(200, json={"access_token": "token"},
                              request=httpx.Request("POST", url))

    def fake_get(url, **_kwargs):
        user = {"sub": "123", "name": "Test User", "email": "test@example.com"}
        return httpx.Response(200, json=user, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)


def test_google_sign_in_url(google_client):
    params = _start_google_sign_in(google_client)
    assert params["client_id"] == ["test-client"]
    assert params["scope"] == ["openid email profile"]
    assert params["state"][0]
    assert google_client.get("/api/session").status_code == 401


def test_google_callback_signs_in(google_client, monkeypatch):
    _fake_google(monkeypatch)
    state = _start_google_sign_in(google_client, "/inbox")["state"][0]
    response = google_client.get("/api/auth/google/callback",
                                 params={"code": "abc", "state": state}, follow_redirects=False)
    assert response.headers["location"] == "/auth/callback?returnTo=/inbox"
    user = google_client.get("/api/session").json()["user"]
    assert user == {"id": "123", "name": "Test User", "email": "test@example.com"}
    assert google_client.post("/api/auth/logout").status_code == 204
    assert google_client.get("/api/session").status_code == 401


def test_google_callback_rejects_wrong_state(google_client, monkeypatch):
    _fake_google(monkeypatch)
    _start_google_sign_in(google_client)
    response = google_client.get("/api/auth/google/callback",
                                 params={"code": "abc", "state": "wrong"}, follow_redirects=False)
    assert response.headers["location"] == "/auth/callback?error=invalid_state"
    assert google_client.get("/api/session").status_code == 401


def test_google_callback_cancelled(google_client):
    _start_google_sign_in(google_client)
    response = google_client.get("/api/auth/google/callback",
                                 params={"error": "access_denied"}, follow_redirects=False)
    assert response.headers["location"] == "/auth/callback?error=access_denied"
