"""Shared fixtures: an app over a fresh data dir, offline and with the worker stopped.

- `make_app(**kw)` builds another app on the same data dir (restart tests).
- `client` is a TestClient (lifespan runs); the user starts signed out.
- `signed_in` signs that client in through /auth/google.
"""
import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def server_env(monkeypatch):
    """Offline, deterministic environment. Set before create_app reads it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("FAKE_GREENHOUSE", "true")
    monkeypatch.setenv("RESUME_PARSE_STEP_MS", "0")
    monkeypatch.setenv("SEED_BANK_FROM_PROFILE", "false")
    monkeypatch.setenv("AGENT_SHOW_BROWSER", "false")
    monkeypatch.setenv("AGENT_SLOW_MO_MS", "0")


@pytest.fixture
def make_app(data_dir, server_env):  # pylint: disable=redefined-outer-name,unused-argument
    def build(**kwargs):
        kwargs.setdefault("start_worker", False)
        built = create_app(data_dir=data_dir, **kwargs)
        built.state.config.submit_real_form = False  # tests opt in explicitly
        return built
    return build


@pytest.fixture
def app(make_app):  # pylint: disable=redefined-outer-name
    return make_app()


@pytest.fixture
def client(app):  # pylint: disable=redefined-outer-name
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client):  # pylint: disable=redefined-outer-name
    response = client.post("/api/auth/google", json={"returnTo": "/"})
    assert response.status_code == 200
    return client
