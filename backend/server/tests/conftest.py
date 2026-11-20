"""Shared fixtures: an app over a fresh data folder, offline, signed in, worker stopped."""
import pytest

from agent.jobs.job_feed import JobFeed
from agent.jobs.job_link import UnsupportedLink
from server.app import create_app
from server.config import load_config
from server.tests import fake_site
from server.tests.clerk_helpers import (ALICE, ORIGIN, FakeClerkUsers, fake_verifier,
                                        signed_in_client)


def pytest_configure(config):
    """Register the e2e marker."""
    config.addinivalue_line(
        "markers", "e2e: whole flows through the real worker thread and headless Chromium "
                   "(select with -m e2e, skip with -m 'not e2e')")


@pytest.fixture(name="data_dir")
def fixture_data_dir(tmp_path):
    """A data folder that doesn't exist yet."""
    return tmp_path / "data"


@pytest.fixture(name="user_dir")
def fixture_user_dir(data_dir):
    """Alice's own folder inside the data folder."""
    return data_dir / "users" / ALICE


@pytest.fixture(name="server_env")
def fixture_server_env(monkeypatch):
    """An offline, deterministic environment, set before create_app reads it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("RESUME_PARSE_STEP_MS", "0")
    monkeypatch.setenv("AGENT_SHOW_BROWSER", "false")
    monkeypatch.setenv("AGENT_SLOW_MO_MS", "0")
    monkeypatch.setenv("CONFIRM_TIMEOUT_S", "90")


@pytest.fixture(name="fake_forms", autouse=True)
def fixture_fake_forms(monkeypatch):
    """The fakecompany test postings open the local fake forms."""
    monkeypatch.setattr("server.agent_bridge.form_for", fake_site.form_for)


@pytest.fixture(name="unfillable")
def fixture_unfillable(monkeypatch):
    """Every real (non-fake) link acts like a site the agent can't fill, without going online."""
    def refuse(link):
        raise UnsupportedLink(f"AutoApply can't fill {link.site.title()} forms yet.")
    monkeypatch.setattr("server.agent_bridge.form_for",
                        lambda link: fake_site.form_for(link, real=refuse))


@pytest.fixture(name="make_app")
def fixture_make_app(data_dir, server_env):  # pylint: disable=unused-argument  # sets the env
    """Builds apps on the same data folder; afterwards, closes the form windows they hold.

    Each app trusts the test signing key, lists only the fake job boards, and has Alice's
    account open, with her store, bank and worker on app.state for the tests to reach.
    """
    built_apps = []

    def build(start_worker: bool = False, **overrides):
        config = load_config(data_dir)
        config.allowed_origins = (ORIGIN,)
        config.submit_real_form = False  # tests opt in explicitly
        for name, value in overrides.items():
            setattr(config, name, value)
        built = create_app(config=config, start_worker=start_worker,
                           verifier=fake_verifier())
        built.state.accounts.clerk_users = FakeClerkUsers()
        built.state.job_feed = JobFeed(config.data_dir / "job_feed.json",
                                       boards=fake_site.fake_boards(), keep=None)
        alice = built.state.accounts.get(ALICE)
        built.state.store, built.state.answer_bank = alice.store, alice.bank
        built.state.worker = alice.worker
        built_apps.append(built)
        return built
    yield build
    for built in built_apps:
        for account in built.state.accounts.all():
            account.worker.close_forms_for_tests()


@pytest.fixture(name="app")
def fixture_app(make_app):
    """An app over a fresh data folder."""
    return make_app()


@pytest.fixture(name="client")
def fixture_client(app):
    """A TestClient with the lifespan running, signed in as Alice."""
    with signed_in_client(app) as test_client:
        yield test_client
