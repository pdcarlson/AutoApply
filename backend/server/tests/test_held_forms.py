"""Filled forms held open for the review: when they're kept, and every way they get closed.

Only the local fake Greenhouse form is used (FAKE_GREENHOUSE, set by conftest).
"""
# pylint: disable=redefined-outer-name,unused-argument
import threading
import urllib.request

import pytest
from fastapi.testclient import TestClient

from server import jobs
from server.applications import REFILLED
from server.tests.job_helpers import (add_job, apply, job_detail, seed_fake_form_answers,
                                      set_up_profile, wait_for_state)

SECOND_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1002"  # also the fake form


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.greenhouse_form.urlopen", refuse)


@pytest.fixture
def profile(client, app):
    set_up_profile(client)
    seed_fake_form_answers(app)


def make_ready(client, app, url) -> str:
    job = add_job(client, url)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["state"] == "ready"
    return job["id"]


def held(app, job_id):
    return app.state.worker.forms.get(job_id)


def test_ready_jobs_each_keep_their_window(client, app, profile):
    """The worker moves on to the next job while earlier ones stay open for review."""
    first = make_ready(client, app, "https://job-boards.greenhouse.io/fakecompany/jobs/1001")
    second = make_ready(client, app, SECOND_URL)
    assert held(app, first).alive and held(app, second).alive
    assert app.state.worker.forms.job_ids() == [first, second]
    assert held(app, first).call(lambda form: form.usable())


def test_skip_closes_the_window(client, app, profile):
    job_id = make_ready(client, app, SECOND_URL)
    session = held(app, job_id)
    assert client.post(f"/api/jobs/{job_id}/skip").status_code == 204
    assert not session.alive and held(app, job_id) is None


def test_delete_account_closes_every_window(client, app, profile):
    first = make_ready(client, app, "https://job-boards.greenhouse.io/fakecompany/jobs/1001")
    second = make_ready(client, app, SECOND_URL)
    sessions = [held(app, first), held(app, second)]
    assert client.delete("/api/account").status_code == 204
    assert not any(s.alive for s in sessions) and len(app.state.worker.forms) == 0


def test_a_job_that_stops_being_ready_loses_its_window(client, app, profile):
    """The worker's safety net closes windows whose job left `ready` some other way."""
    job_id = make_ready(client, app, SECOND_URL)
    session = held(app, job_id)
    with app.state.store.tx() as db:
        jobs.find(db, job_id)["state"] = "open"
    app.state.worker.run_next()
    assert not session.alive and held(app, job_id) is None


def test_the_oldest_window_closes_past_the_limit(client, app, profile):
    """Past HELD_FORMS_MAX the oldest window closes; its Submit fills the form again."""
    app.state.config.held_forms_max = 1
    first = make_ready(client, app, "https://job-boards.greenhouse.io/fakecompany/jobs/1001")
    oldest = held(app, first)
    second = make_ready(client, app, SECOND_URL)
    assert not oldest.alive and app.state.worker.forms.job_ids() == [second]

    app.state.config.submit_real_form = True
    response = client.post(f"/api/jobs/{first}/submit")
    assert response.status_code == 200, response.text
    timeline = client.get(f"/api/applications/app-{first}").json()["timeline"]
    assert REFILLED in [e["text"] for e in timeline]


def test_holding_can_be_turned_off(client, app, profile):
    app.state.config.held_forms_max = 0
    job_id = make_ready(client, app, SECOND_URL)
    assert len(app.state.worker.forms) == 0
    app.state.config.submit_real_form = True
    assert client.post(f"/api/jobs/{job_id}/submit").status_code == 200


def test_shutdown_closes_the_windows(make_app):
    """The lifespan's worker.stop() closes every held window, with the real worker thread."""
    app = make_app(start_worker=True)
    with TestClient(app) as client:
        set_up_profile(client)
        seed_fake_form_answers(app)
        job = add_job(client)
        apply(client, job["id"])
        assert wait_for_state(client, job["id"], ("ready", "open", "handoff"))["state"] == "ready"
        session = held(app, job["id"])
        assert session.alive
        worker_threads = {t.name for t in threading.enumerate()}
        assert f"form-{job['id']}" in worker_threads
    assert not session.alive and len(app.state.worker.forms) == 0
    assert f"form-{job['id']}" not in {t.name for t in threading.enumerate()}
