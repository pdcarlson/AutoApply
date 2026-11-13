"""Konefal's modules keep working after the light refactor (spec 2.4, WP2)."""
# pylint: disable=redefined-outer-name,unused-argument  # pytest fixtures
import json
import subprocess
import sys

import pytest

from server import konefal
from server.common_answers import COMMON_QUESTION_KEYS
from server.tests.conftest import KONEFAL_BANK, _digest

ABM = konefal.AnswerBankManager


@pytest.fixture
def bank_file(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "bank.json"
    monkeypatch.setattr(ABM, "bankPath", ABM.bankPath)  # restored after the test
    ABM.setBankPath(str(path))
    return path


def test_default_bank_path_is_next_to_the_module():
    assert konefal.AUTOAPPLY_DIR.joinpath("Bank.json").samefile(KONEFAL_BANK)
    assert str(konefal.AUTOAPPLY_DIR) in sys.path
    assert sys.path.index(str(konefal.AUTOAPPLY_DIR)) > 0  # appended, never shadows


def test_save_single_response_for_a_new_user(bank_file):
    ABM.SaveSingleResponse("u", "q", "a")
    assert ABM.LoadData("u", "q") == "a"
    assert json.loads(bank_file.read_text(encoding="utf-8")) == {"userdata": {"u": {"q": "a"}}}
    assert not list(bank_file.parent.glob("*.tmp"))


def test_save_response_dictionary_merges_for_an_existing_user(bank_file):
    ABM.SaveResponseDictionary("u", {"a": "1", "b": "2"})
    ABM.SaveResponseDictionary("u", {"b": "3", "c": "4"})
    assert ABM.LoadUser("u") == {"a": "1", "b": "3", "c": "4"}


def test_utf8_round_trip(bank_file):
    ABM.SaveSingleResponse("u", "selfId", "“I don’t wish to answer”")
    assert ABM.LoadData("u", "selfId") == "“I don’t wish to answer”"
    assert "“I don’t wish to answer”" in bank_file.read_text(encoding="utf-8")


def test_delete_response(bank_file):
    ABM.SaveSingleResponse("u", "q", "a")
    assert ABM.DeleteResponse("u", "q") is True
    assert ABM.DeleteResponse("u", "q") is False
    assert ABM.DeleteResponse("nobody", "q") is False
    assert ABM.LoadUser("u") == {}


def test_load_questions_has_the_common_keys_and_the_originals():
    questions = konefal.Onboarding.loadQuestions()
    for key in COMMON_QUESTION_KEYS:
        assert key in questions
        prompt, bank_key, category = questions[key]
        assert prompt and bank_key == key
        assert category in {"Eligibility", "Education", "Logistics", "Pay", "Experience", "Self-ID"}
    assert questions["0"] == ["What is your full name?", "Name"]


def test_ask_questions_no_longer_raises(bank_file, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *args: "x")
    konefal.Onboarding.askQuestions(-1)
    saved = ABM.LoadUser(-1)
    assert saved["Name"] == "x" and saved["gender"] == "x"


def test_ask_question_and_save_answer(bank_file, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *args: "Jo")
    konefal.Onboarding.askQuestion(-1, "0")
    konefal.Onboarding.saveAnswer(-1, "1", "21")
    assert ABM.LoadUser(-1) == {"Name": "Jo", "Age": "21"}


def test_read_resume_handles_case_and_missing_files(tmp_path):
    assert konefal.resumeRead.isHeader("EDUCATION")
    assert konefal.resumeRead.isHeader("Skills:")
    assert not konefal.resumeRead.isHeader("Hudson Valley Institute of Technology")
    assert konefal.resumeRead.readResume(str(tmp_path / "nope.pdf")) is None
    assert konefal.resumeRead.sectionsFromLines(["Jo", "", "SKILLS", "Python"]) == {
        "Other": ["Jo"], "SKILLS": ["Python"]}


def test_konefal_folder_still_imports_on_its_own():
    """Their workflow: `python -c "import ..."` from inside backend/AutoApply."""
    result = subprocess.run(
        [sys.executable, "-c", "import AnswerBankManager, Onboarding, resumeRead"],
        cwd=konefal.AUTOAPPLY_DIR, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr


def test_bank_json_is_unchanged_so_far(konefal_bank_untouched):
    """The session fixture checks again at the very end."""
    assert _digest(KONEFAL_BANK) == konefal_bank_untouched != "missing"
