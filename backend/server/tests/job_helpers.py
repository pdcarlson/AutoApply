"""Helpers for tests that add, apply and run jobs against the fake Greenhouse and Ashby forms."""
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import BrowserType

import server.runs.run_setup

# conftest turns FAKE_GREENHOUSE on, so these map to backend/agent/tests/fake_forms.
FAKE_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1001"
FAKE_ASHBY_URL = "https://jobs.ashbyhq.com/fakecompany/00000000-0000-4000-8000-000000001001"
SECOND_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1002"
# A real-looking Ashby link. Tests use it with the `unfillable` fixture, so it never goes online.
ASHBY_URL = "https://jobs.ashbyhq.com/acme/0a1b2c3d"
SPONSORSHIP = "Will you now or in the future require visa sponsorship to work in the United States?"
WHY_HERE = "Why do you want to work here?"
EXAMPLE_PDF = Path(__file__).resolve().parents[2] / "agent" / "applicant" / "example_resume.pdf"


def refuse_network(monkeypatch, *modules: str) -> None:
    """Make every urlopen, and the Greenhouse form's and each module's own, fail the test."""
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    for module in ("agent.forms.greenhouse_form", *modules):
        monkeypatch.setattr(f"{module}.urlopen", refuse)


def upload_resume(client, timeout: float = 30.0) -> dict:
    """Upload agent/applicant/example_resume.pdf and wait for the parse to finish."""
    response = client.post("/api/resume", files={
        "file": ("example_resume.pdf", EXAMPLE_PDF.read_bytes(), "application/pdf")})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + timeout
    while True:
        parse = client.get("/api/resume/parse").json()
        if parse["status"] != "parsing":
            assert parse["status"] == "done", parse
            return parse
        assert time.monotonic() < deadline, "resume parse timed out"
        time.sleep(0.05)


def set_up_profile(client, *, resume: bool = True, confirm: bool = True) -> None:
    """Sign in, upload the example resume, answer the common questions, and confirm.

    The common answers cover sponsorship only in setup's own wording, which doesn't match the
    fake form's label, so a run still asks about it.
    """
    assert client.post("/api/auth/google", json={"returnTo": "/"}).status_code == 200
    if resume:
        upload_resume(client)
    common = client.get("/api/common-answers").json()
    common.update(workAuthorized="Yes", needsSponsorship="No")
    assert client.put("/api/common-answers", json=common).status_code == 200
    if confirm:
        assert client.post("/api/profile/confirm").status_code == 200


def add_job(client, url: str = FAKE_URL) -> dict:
    """Add a job from its link and return the API Job."""
    response = client.post("/api/jobs", json={"url": url})
    assert response.status_code == 201, response.text
    return response.json()


def apply(client, *job_ids: str) -> dict:
    """Press Apply on the jobs and return {queued, deferred}."""
    response = client.post("/api/jobs/apply", json={"jobIds": list(job_ids)})
    assert response.status_code == 200, response.text
    return response.json()


def make_ready(client, app, url: str = FAKE_URL) -> str:
    """Add, apply and fill a fake-form job up to `ready`; return its id."""
    job = add_job(client, url)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["state"] == "ready"
    return job["id"]


def seed_fake_form_answers(app, why: str = "I like building tools people use.") -> dict:
    """Bank answers for the fake form's two required questions; return {label: answer id}."""
    bank = app.state.answer_bank
    sponsorship = bank.upsert_by_question(SPONSORSHIP, "No", origin="manual", source="Test")
    why_here = bank.upsert_by_question(WHY_HERE, why, company="Fake Company", origin="reply",
                                       source="Test")
    return {SPONSORSHIP: sponsorship["id"], WHY_HERE: why_here["id"]}


def use_fake_form_variant(monkeypatch, query: str) -> None:
    """Make fills from now on use one of the fake form's test-only variants.

    "confirm_ms=N" confirms N ms after Submit, "code=1" asks for an emailed code instead, and
    "protect=ssn|password|captcha" adds a step the agent must leave to the person.
    """
    original = server.runs.run_setup.make_form

    def make_form(job, config):
        form = original(job, config)
        assert form.url and form.url.startswith("file://"), "only the local fake form"
        form.url += f"?{query}"
        return form
    monkeypatch.setattr(server.runs.run_setup, "make_form", make_form)


def record_launches(monkeypatch) -> list:
    """Record the options of every Chromium launch from now on."""
    seen, original = [], BrowserType.launch

    def spy(self, *args, **kwargs):
        seen.append(kwargs)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(BrowserType, "launch", spy)
    return seen


def job_detail(client, job_id: str) -> dict:
    """Return the API JobDetail for one job."""
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_state(client, job_id: str, states: tuple[str, ...], timeout: float = 60.0) -> dict:
    """Poll GET /jobs/:id until the job is in one of `states`; return its detail."""
    deadline = time.monotonic() + timeout
    while True:
        detail = job_detail(client, job_id)
        if detail["state"] in states:
            return detail
        assert time.monotonic() < deadline, f"job stuck in {detail['state']}"
        time.sleep(0.1)


def wait_until(check, seconds: float = 15.0) -> bool:
    """Poll `check()` until it is true; return False if it never was."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False
