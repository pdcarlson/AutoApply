"""API tests against a throwaway SQLite database (no Postgres needed to run them)."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# pylint: disable=wrong-import-position
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_apply_from_link_and_duplicate():
    url = "https://jobs.lever.co/kestrelhealth/abc-123"
    first = client.post("/api/applications", json={"url": url})
    assert first.status_code == 201
    assert first.json()["status"] == "queued"
    assert first.json()["company"] == "kestrelhealth"

    second = client.post("/api/applications", json={"url": url})
    assert second.status_code == 409


def test_unsupported_link_rejected():
    res = client.post("/api/applications", json={"url": "https://www.linkedin.com/jobs/view/1"})
    assert res.status_code == 400


def test_answer_bank_crud():
    created = client.post("/api/answers", json={"question": "Earliest start date", "answer": "May 2027"})
    answer_id = created.json()["id"]
    client.put(f"/api/answers/{answer_id}", json={"question": "Earliest start date", "answer": "June 2027"})
    assert client.get("/api/answers").json()[0]["answer"] == "June 2027"
    assert client.delete(f"/api/answers/{answer_id}").status_code == 204


def test_resume_wrong_type():
    res = client.post("/api/profile/resume", files={"file": ("resume.png", b"x", "image/png")})
    assert res.status_code == 400
