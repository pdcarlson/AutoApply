"""AnswerBankFile saves, merges and deletes answers in its JSON file."""
import json

import pytest

from onboarding.answer_bank_file import AnswerBankFile


@pytest.fixture(name="bank_file")
def fixture_bank_file(tmp_path):
    """An AnswerBankFile in a folder that doesn't exist yet."""
    return AnswerBankFile(tmp_path / "nested" / "bank.json")


def test_save_answer_for_a_new_user(bank_file):
    """Saving one answer creates the folder and the user, and leaves no temporary file."""
    bank_file.save_answer("u", "q", "a")
    assert bank_file.load_user("u") == {"q": "a"}
    assert json.loads(bank_file.path.read_text(encoding="utf-8")) == {"userdata": {"u": {"q": "a"}}}
    assert not list(bank_file.path.parent.glob("*.tmp"))


def test_save_answers_merges_into_what_the_user_has(bank_file):
    """Saving several answers keeps the user's other answers."""
    bank_file.save_answers("u", {"a": "1", "b": "2"})
    bank_file.save_answers("u", {"b": "3", "c": "4"})
    assert bank_file.load_user("u") == {"a": "1", "b": "3", "c": "4"}


def test_utf8_round_trip(bank_file):
    """Curly quotes survive a save and a load."""
    bank_file.save_answer("u", "selfId", "“I don’t wish to answer”")
    assert bank_file.load_user("u") == {"selfId": "“I don’t wish to answer”"}
    assert "“I don’t wish to answer”" in bank_file.path.read_text(encoding="utf-8")


def test_delete_answer(bank_file):
    """Deleting says whether there was an answer to delete."""
    bank_file.save_answer("u", "q", "a")
    assert bank_file.delete_answer("u", "q") is True
    assert bank_file.delete_answer("u", "q") is False
    assert bank_file.delete_answer("nobody", "q") is False
    assert bank_file.load_user("u") == {}


def test_missing_or_malformed_file_reads_as_empty(bank_file):
    """A bank that doesn't exist, or isn't a JSON object, has no users."""
    assert bank_file.load_user("u") == {}
    bank_file.path.parent.mkdir(parents=True)
    bank_file.path.write_text("[]", encoding="utf-8")
    assert bank_file.load_user("u") == {}
