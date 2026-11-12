"""The Answer bank over AnswerBankManager, and the /answers routes (spec 2.5)."""
import json
from datetime import timedelta

from server.answer_bank import guess_category

ANSWER_KEYS = {"id", "category", "question", "answer", "source", "company", "timesUsed",
               "lastUsedAt", "alsoMatches", "usedOn", "savedRecently"}


def _bank_file(app):
    return app.state.store.path("answer_bank.json")


def _add(client, **overrides):
    body = {"category": "Logistics", "question": "How did you hear about this job?",
            "answer": "LinkedIn", "company": None, **overrides}
    response = client.post("/api/answers", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_matches_the_answer_shape(client, app):
    created = _add(client)
    assert set(created) == ANSWER_KEYS
    assert created["id"].startswith("a-")
    assert created["source"].startswith("You added it · ")
    assert created["timesUsed"] == 0 and created["savedRecently"] is False
    assert created["alsoMatches"] == [] and created["usedOn"] == []

    listed = client.get("/api/answers").json()
    assert [a["id"] for a in listed] == [created["id"]]
    assert set(listed[0]) == ANSWER_KEYS

    patched = client.patch(f"/api/answers/{created['id']}",
                           json={"answer": "A friend", "company": "Fake Company"}).json()
    assert patched["answer"] == "A friend" and patched["company"] == "Fake Company"
    assert patched["question"] == created["question"]

    # Konefal's layout: userdata.local.<id> = record (origin, createdAt are server-only)
    raw = json.loads(_bank_file(app).read_text(encoding="utf-8"))
    record = raw["userdata"]["local"][created["id"]]
    assert record["origin"] == "manual" and record["createdAt"]

    assert client.delete(f"/api/answers/{created['id']}").status_code == 204
    assert client.delete(f"/api/answers/{created['id']}").status_code == 204  # idempotent
    assert client.get("/api/answers").json() == []
    assert client.patch("/api/answers/a-missing", json={"answer": "x"}).json()["code"] == \
        "not_found"


def test_invalid_answers_are_rejected(client):
    for body in ({"category": "Hobbies", "question": "q", "answer": "a", "company": None},
                 {"category": "Pay", "question": "  ", "answer": "a", "company": None},
                 {"category": "Pay", "question": "q", "answer": "", "company": None}):
        response = client.post("/api/answers", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_answer"
    created = _add(client)
    response = client.patch(f"/api/answers/{created['id']}", json={"category": "Nope"})
    assert response.json()["code"] == "invalid_answer"


def test_company_and_global_answers_to_the_same_question_coexist(client, app):
    bank = app.state.answer_bank
    question = "Why do you want to work here?"
    shared = bank.upsert_by_question(question, "Generic", None, origin="reply", source="s")
    own = bank.upsert_by_question(question, "Fake-specific", "Fake Company", origin="reply",
                                  source="s")
    assert shared["id"] != own["id"]
    again = bank.upsert_by_question("why do you want to work  here?", "Updated", "fake company",
                                    origin="reply", source="s")
    assert again["id"] == own["id"] and again["answer"] == "Updated"
    answers = client.get("/api/answers").json()
    assert sorted(a["company"] or "" for a in answers) == ["", "Fake Company"]
    assert all(a["savedRecently"] for a in answers)  # origin reply, created just now


def test_applicable_puts_company_answers_first(app):
    bank = app.state.answer_bank
    bank.create({"question": "Q1", "answer": "global", "category": "Pay", "company": None},
                origin="manual", source="s")
    bank.create({"question": "Q2", "answer": "other", "category": "Pay", "company": "Other Co"},
                origin="manual", source="s")
    bank.create({"question": "Q1", "answer": "fake", "category": "Pay",
                 "company": "Fake Company"}, origin="manual", source="s")
    applicable = bank.applicable("Fake Company")
    assert [r["answer"] for r in applicable] == ["fake", "global"]
    assert applicable[0]["origin"] == "manual"

    answers, ids = bank.projection("Fake Company")
    assert [(a.question, a.answer) for a in answers] == [("Q1", "fake")]
    assert ids == {"q1": applicable[0]["id"]}


def test_legacy_string_values_are_listed_as_records(make_app):
    app = make_app()
    path = _bank_file(app)
    path.write_text(json.dumps({"userdata": {"local": {"Name": "Jo", "Junk": [1, 2]},
                                             "-1": {"Age": "21"}}}), encoding="utf-8")
    bank = app.state.answer_bank
    listed = bank.list()
    assert len(listed) == 1
    assert listed[0]["id"] == "Name" and listed[0]["question"] == "Name"
    assert listed[0]["answer"] == "Jo" and listed[0]["source"] == "Imported"
    assert bank.record("Name")["origin"] == "import"
    bank.update("Name", {"answer": "Joanna"})
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["userdata"]["local"]["Name"]["answer"] == "Joanna"  # written back as a record
    assert raw["userdata"]["local"]["Junk"] == [1, 2]  # ignored, untouched
    assert raw["userdata"]["-1"] == {"Age": "21"}


def test_record_use_tracks_usage(app):
    bank = app.state.answer_bank
    created = bank.create({"question": "Q", "answer": "A", "category": "Pay"}, origin="manual",
                          source="s")
    bank.record_use(created["id"], "Fake Company")
    used = bank.record_use(created["id"], "Other Co", wording="Q (please)")
    assert used["timesUsed"] == 2 and used["lastUsedAt"]
    assert [u["company"] for u in used["usedOn"]] == ["Other Co", "Fake Company"]
    assert used["alsoMatches"] == [{"wording": "Q (please)", "seenOn": "Other Co"}]
    assert bank.record_use("a-missing", "X") is None


def test_saved_recently_expires_after_a_day(app):
    store = app.state.store
    bank = app.state.answer_bank
    created = bank.upsert_by_question("Q", "A", origin="reply", source="s")
    assert bank.get(created["id"])["savedRecently"] is True
    real_clock = store.clock
    store.clock = lambda: real_clock() + timedelta(hours=25)
    assert bank.get(created["id"])["savedRecently"] is False


def test_seed_import_from_profile_reads_but_never_writes_it(make_app, tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    text = json.dumps({"first_name": "A", "answers": [
        {"question": "How did you hear about this job?", "answer": "LinkedIn"},
        {"question": "Are you over 18?", "answer": "Yes"}]})
    profile.write_text(text, encoding="utf-8")
    monkeypatch.setenv("SEED_BANK_FROM_PROFILE", "true")

    from server.config import load_config  # pylint: disable=import-outside-toplevel
    config = load_config(tmp_path / "data")
    config.profile_path = profile
    app = make_app(config=config)
    answers = app.state.answer_bank.list()
    assert {a["question"] for a in answers} == {"How did you hear about this job?",
                                                "Are you over 18?"}
    assert all(a["source"] == "Imported from your agent profile" for a in answers)
    assert profile.read_text(encoding="utf-8") == text
    for answer in answers:
        app.state.answer_bank.delete(answer["id"])
    again = make_app(config=config)  # once per data dir: an emptied bank stays empty
    assert again.state.answer_bank.list() == []


def test_guess_category():
    assert guess_category("Will you require visa sponsorship?") == "Eligibility"
    assert guess_category("What is your GPA?") == "Education"
    assert guess_category("Desired salary") == "Pay"
    assert guess_category("Veteran status") == "Self-ID"
    assert guess_category("How did you hear about this job?") == "Logistics"
    assert guess_category("Why do you want to work here?") == "Experience"


def test_export_includes_answers(signed_in):
    _add(signed_in)
    exported = signed_in.get("/api/account/export").json()
    assert len(exported["answers"]) == 1 and set(exported["answers"][0]) == ANSWER_KEYS


def test_bank_starts_empty_by_default(make_app, tmp_path, monkeypatch):
    """The example profile's answers are test data; they must never appear in a user's bank."""
    monkeypatch.delenv("SEED_BANK_FROM_PROFILE", raising=False)
    from server.config import load_config  # pylint: disable=import-outside-toplevel
    config = load_config(tmp_path / "data")
    assert config.seed_bank_from_profile is False
    app = make_app(config=config)
    assert app.state.answer_bank.list() == []
