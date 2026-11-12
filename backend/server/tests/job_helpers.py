"""Helpers for tests that add, apply and run jobs against the fake Greenhouse form.

The fixtures in conftest set FAKE_GREENHOUSE=true and ANTHROPIC_API_KEY="", so FAKE_URL maps
to backend/agent/tests/fake_forms and nothing reaches the network or Claude.
"""
import time
from pathlib import Path

import server.worker

FAKE_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1001"
ASHBY_URL = "https://jobs.ashbyhq.com/acme/0a1b2c3d"
SPONSORSHIP = "Will you now or in the future require visa sponsorship to work in the United States?"
WHY_HERE = "Why do you want to work here?"
EXAMPLE_PDF = Path(__file__).resolve().parents[2] / "agent" / "applicant" / "example_resume.pdf"


def upload_resume(client, timeout: float = 30.0) -> dict:
    """Uploads agent/applicant/example_resume.pdf and waits for the parse to finish."""
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
    """Signs in, uploads the example resume, answers the common questions, confirms.

    The common answers cover sponsorship only in setup's own wording, which doesn't match the
    fake form's label, so a run still asks about it (spec 6.2).
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
    response = client.post("/api/jobs", json={"url": url})
    assert response.status_code == 201, response.text
    return response.json()


def apply(client, *job_ids: str) -> dict:
    response = client.post("/api/jobs/apply", json={"jobIds": list(job_ids)})
    assert response.status_code == 200, response.text
    return response.json()


def seed_fake_form_answers(app, why: str = "I like building tools people use.") -> dict:
    """Bank answers for the fake form's two required questions. Returns {label: answer id}."""
    bank = app.state.answer_bank
    sponsorship = bank.upsert_by_question(SPONSORSHIP, "No", origin="manual", source="Test")
    why_here = bank.upsert_by_question(WHY_HERE, why, company="Fake Company", origin="reply",
                                       source="Test")
    return {SPONSORSHIP: sponsorship["id"], WHY_HERE: why_here["id"]}


def use_fake_form_variant(monkeypatch, query: str) -> None:
    """Fills from now on use the fake form's test-only variant `query` (see the page's script):
    "confirm_ms=N" confirms N ms after Submit, "code=1" asks for an emailed code instead."""
    original = server.worker.make_form

    def make_form(job, config):
        form = original(job, config)
        assert form.url and form.url.startswith("file://"), "only the local fake form"
        form.url += f"?{query}"
        return form
    monkeypatch.setattr(server.worker, "make_form", make_form)


def job_detail(client, job_id: str) -> dict:
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_state(client, job_id: str, states: tuple[str, ...], timeout: float = 60.0) -> dict:
    """Polls GET /jobs/:id until the job is in one of `states`."""
    deadline = time.monotonic() + timeout
    while True:
        detail = job_detail(client, job_id)
        if detail["state"] in states:
            return detail
        assert time.monotonic() < deadline, f"job stuck in {detail['state']}"
        time.sleep(0.1)
