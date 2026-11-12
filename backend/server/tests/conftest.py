"""Shared fixtures: an app over a fresh data dir, offline and with the worker stopped.

- `make_app(**kw)` builds another app on the same data dir (restart tests).
- `client` is a TestClient (lifespan runs); the user starts signed out.
- `signed_in` signs that client in through /auth/google.
- Every session checks that backend/AutoApply/Bank.json (a tracked fixture) is never written.
"""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

KONEFAL_BANK = Path(__file__).resolve().parents[2] / "AutoApply" / "Bank.json"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: whole flows through the real worker thread and headless Chromium "
                   "(select with -m e2e, skip with -m 'not e2e')")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


@pytest.fixture(scope="session", autouse=True)
def konefal_bank_untouched():
    """Bank.json must stay byte-for-byte the same across the whole test session."""
    before = _digest(KONEFAL_BANK)
    yield before
    assert _digest(KONEFAL_BANK) == before, "backend/AutoApply/Bank.json was modified"


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
