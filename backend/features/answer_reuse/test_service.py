"""Exact-match answer reuse (US9)."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# pylint: disable=wrong-import-position
import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Answer, User
from features.answer_reuse.service import AnswerReuse, normalize_question

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def new_bank():
    db = SessionLocal()
    user = User(email="joe@example.com")
    db.add(user)
    db.commit()
    return db, AnswerReuse(db, user.id)


def test_identical_questions_normalize_the_same():
    plain = normalize_question("Are you legally authorized to work in the US?")
    assert normalize_question("  are you legally authorized to work in the US *") == plain
    assert normalize_question("Are you legally  authorized to work in the US? (required)") == plain
    assert normalize_question("Are you authorized to work in the US?") != plain


def test_answer_is_reused_and_counted():
    db, bank = new_bank()
    bank.remember("Earliest start date", "May 24, 2027")

    reused = bank.reuse("Earliest start date *")
    assert reused.text == "May 24, 2027"
    assert reused.confidence == 100
    assert reused.source.startswith("answer bank #")
    assert db.get(Answer, reused.answer_id).times_used == 1
    db.close()


def test_unknown_question_is_not_guessed():
    db, bank = new_bank()
    bank.remember("Earliest start date", "May 24, 2027")
    assert bank.reuse("Why do you want to work here?") is None
    db.close()


def test_remember_updates_instead_of_duplicating():
    db, bank = new_bank()
    bank.remember("Will you require sponsorship?", "No")
    bank.remember("will you require sponsorship", "Yes")
    rows = db.query(Answer).all()
    assert len(rows) == 1
    assert rows[0].answer == "Yes"
    db.close()


def test_other_students_answers_are_never_used():
    db, bank = new_bank()
    other = User(email="plia@example.com")
    db.add(other)
    db.commit()
    AnswerReuse(db, other.id).remember("Earliest start date", "June 2027")
    assert bank.reuse("Earliest start date") is None
    db.close()


def test_blank_answers_are_refused():
    db, bank = new_bank()
    with pytest.raises(ValueError):
        bank.remember("Earliest start date", "   ")
    db.close()


def test_remember_and_match_routes():
    client.post("/api/answers/remember", json={"question": "How did you hear about us?",
                                               "answer": "Company careers page"})
    client.post("/api/answers/remember", json={"question": "How did you hear about us",
                                               "answer": "A friend"})
    assert len(client.get("/api/answers").json()) == 1

    match = client.get("/api/answers/match", params={"question": "How did you hear about us? *"})
    assert match.json()["answer"] == "A friend"
    assert client.get("/api/answers/match", params={"question": "Pronouns"}).json() is None
