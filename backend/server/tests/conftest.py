"""Shared fixtures: an app over a fresh data folder, offline and with the worker stopped."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.jobs.job_link import UnsupportedLink
from server.app import create_app

# A tracked file in backend/AutoApply/ that the server must never write to
AUTOAPPLY_BANK = Path(__file__).resolve().parents[2] / "AutoApply" / "Bank.json"


def pytest_configure(config):
    """Register the e2e marker."""
    config.addinivalue_line(
        "markers", "e2e: whole flows through the real worker thread and headless Chromium "
                   "(select with -m e2e, skip with -m 'not e2e')")


def file_digest(path: Path) -> str:
    """Return the file's SHA-256, or "missing"."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


@pytest.fixture(name="autoapply_bank_untouched", scope="session", autouse=True)
def fixture_autoapply_bank_untouched():
    """Bank.json must stay byte-for-byte the same across the whole test session."""
    before = file_digest(AUTOAPPLY_BANK)
    yield before
    assert file_digest(AUTOAPPLY_BANK) == before, "backend/AutoApply/Bank.json was modified"


@pytest.fixture(name="data_dir")
def fixture_data_dir(tmp_path):
    """A data folder that doesn't exist yet."""
    return tmp_path / "data"


@pytest.fixture(name="server_env")
def fixture_server_env(monkeypatch):
    """An offline, deterministic environment, set before create_app reads it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("FAKE_GREENHOUSE", "true")
    monkeypatch.setenv("RESUME_PARSE_STEP_MS", "0")
    monkeypatch.setenv("SEED_BANK_FROM_PROFILE", "false")
    monkeypatch.setenv("AGENT_SHOW_BROWSER", "false")
    monkeypatch.setenv("AGENT_SLOW_MO_MS", "0")
    monkeypatch.setenv("CONFIRM_TIMEOUT_S", "90")


@pytest.fixture(name="unfillable")
def fixture_unfillable(monkeypatch):
    """Every real (non-fake) link acts like a site the agent can't fill, without going online."""
    def refuse(link):
        raise UnsupportedLink(f"AutoApply can't fill {link.site.title()} forms yet.")
    monkeypatch.setattr("server.agent_bridge.form_for", refuse)


@pytest.fixture(name="make_app")
def fixture_make_app(data_dir, server_env):  # pylint: disable=unused-argument  # sets the env
    """Builds apps on the same data folder; afterwards, closes the form windows they hold."""
    built_apps = []

    def build(**kwargs):
        kwargs.setdefault("start_worker", False)
        built = create_app(data_dir=data_dir, **kwargs)
        built.state.config.submit_real_form = False  # tests opt in explicitly
        built_apps.append(built)
        return built
    yield build
    for built in built_apps:
        closer = getattr(built.state.worker, "close_forms_for_tests", None)
        if closer is not None:
            closer()


@pytest.fixture(name="app")
def fixture_app(make_app):
    """An app over a fresh data folder."""
    return make_app()


@pytest.fixture(name="client")
def fixture_client(app):
    """A TestClient with the lifespan running; the user starts signed out."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(name="signed_in")
def fixture_signed_in(client):
    """The client, signed in through /auth/google."""
    response = client.post("/api/auth/google", json={"returnTo": "/"})
    assert response.status_code == 200
    return client
