"""Finishing a protected step from Needs you (US8, UC4)."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# pylint: disable=wrong-import-position
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Application

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def queue_and_hand_off(url="https://boards.greenhouse.io/northwind/jobs/4412093"):
    app_id = client.post("/api/applications", json={"url": url}).json()["id"]
    db = SessionLocal()
    db.get(Application, app_id).status = "needs_you"
    db.commit()
    db.close()
    return app_id


def test_student_finished_it_on_the_site():
    app_id = queue_and_hand_off()
    res = client.post(f"/api/applications/{app_id}/handoff-done", json={"outcome": "submitted"})
    assert res.status_code == 200
    assert res.json()["status"] == "submitted"
    assert res.json()["submitted_at"] is not None


def test_retry_sends_it_back_to_the_agent():
    app_id = queue_and_hand_off()
    res = client.post(f"/api/applications/{app_id}/handoff-done", json={"outcome": "retry"})
    assert res.json()["status"] == "queued"


def test_only_needs_you_applications_can_be_resumed():
    url = "https://jobs.lever.co/kestrelhealth/abc-123"
    app_id = client.post("/api/applications", json={"url": url}).json()["id"]
    res = client.post(f"/api/applications/{app_id}/handoff-done", json={"outcome": "retry"})
    assert res.status_code == 409


def test_unknown_outcome_rejected():
    app_id = queue_and_hand_off()
    res = client.post(f"/api/applications/{app_id}/handoff-done", json={"outcome": "maybe"})
    assert res.status_code == 422
