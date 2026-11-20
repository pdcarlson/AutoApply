"""The modules in backend/AutoApply/ load and work as the server uses them."""
# pylint: disable=unused-argument  # `bank_file` points the bank at a temporary file
import json
import subprocess
import sys

import pytest

from server import autoapply_modules
from server.common_answers import COMMON_QUESTION_KEYS
from server.tests.job_helpers import EXAMPLE_PDF

ABM = autoapply_modules.AnswerBankManager
USER = autoapply_modules.Onboarding.User


@pytest.fixture(name="bank_file")
def fixture_bank_file(tmp_path, monkeypatch):
    """Points AnswerBankManager at a bank file in a fresh folder for one test."""
    path = tmp_path / "nested" / "bank.json"
    monkeypatch.setattr(ABM, "bankPath", ABM.bankPath)  # restored after the test
    ABM.setBankPath(str(path))
    return path


def test_folder_is_appended_to_sys_path():
    """The folder is appended to sys.path, after everything of ours."""
    assert str(autoapply_modules.AUTOAPPLY_DIR) in sys.path
    assert sys.path.index(str(autoapply_modules.AUTOAPPLY_DIR)) > 0  # appended, never shadows


def test_save_single_response_for_a_new_user(bank_file):
    """Saving one answer creates the user and leaves no temporary file."""
    ABM.SaveSingleResponse("u", "q", "a")
    assert ABM.LoadData("u", "q") == "a"
    assert json.loads(bank_file.read_text(encoding="utf-8")) == {"userdata": {"u": {"q": "a"}}}
    assert not list(bank_file.parent.glob("*.tmp"))


def test_save_response_dictionary_merges_for_an_existing_user(bank_file):
    """Saving several answers merges them into what the user already has."""
    ABM.SaveResponseDictionary("u", {"a": "1", "b": "2"})
    ABM.SaveResponseDictionary("u", {"b": "3", "c": "4"})
    assert ABM.LoadUser("u") == {"a": "1", "b": "3", "c": "4"}


def test_utf8_round_trip(bank_file):
    """Curly quotes survive a save and a load."""
    ABM.SaveSingleResponse("u", "selfId", "“I don’t wish to answer”")
    assert ABM.LoadData("u", "selfId") == "“I don’t wish to answer”"
    assert "“I don’t wish to answer”" in bank_file.read_text(encoding="utf-8")


def test_delete_response(bank_file):
    """Deleting says whether there was an answer to delete."""
    ABM.SaveSingleResponse("u", "q", "a")
    assert ABM.DeleteResponse("u", "q") is True
    assert ABM.DeleteResponse("u", "q") is False
    assert ABM.DeleteResponse("nobody", "q") is False
    assert ABM.LoadUser("u") == {}


def test_load_questions_has_the_common_keys_and_the_originals():
    """The onboarding catalog has every common question and its original ones."""
    questions = autoapply_modules.Onboarding.loadQuestions()
    for key in COMMON_QUESTION_KEYS:
        assert key in questions
        prompt, bank_key, category = questions[key]
        assert prompt and bank_key == key
        assert category in {"Eligibility", "Education", "Logistics", "Pay", "Experience", "Self-ID"}
    assert questions["0"] == ["What is your full name?", "Name"]


def test_ask_questions_no_longer_raises(bank_file, monkeypatch):
    """Asking every onboarding question saves each reply."""
    monkeypatch.setattr("builtins.input", lambda *args: "x")
    autoapply_modules.Onboarding.askQuestions(-1)
    saved = ABM.LoadUser(-1)
    assert saved["Name"] == "x" and saved["gender"] == "x"


def test_ask_question_and_save_answer(bank_file, monkeypatch):
    """Asking one question and saving one answer both write the bank."""
    monkeypatch.setattr("builtins.input", lambda *args: "Jo")
    autoapply_modules.Onboarding.askQuestion(-1, "0")
    autoapply_modules.Onboarding.saveAnswer(-1, "1", "21")
    assert ABM.LoadUser(-1) == {"Name": "Jo", "Age": "21"}


def test_read_resume_handles_case_and_missing_files(tmp_path):
    """Headers match in any case, and a missing file reads as None."""
    assert autoapply_modules.resumeRead.isHeader("EDUCATION")
    assert autoapply_modules.resumeRead.isHeader("Skills:")
    assert not autoapply_modules.resumeRead.isHeader("Hudson Valley Institute of Technology")
    assert autoapply_modules.resumeRead.readResume(str(tmp_path / "nope.pdf")) is None
    assert autoapply_modules.resumeRead.sectionsFromLines(["Jo", "", "SKILLS", "Python"]) == {
        "Other": ["Jo"], "SKILLS": ["Python"]}


def test_autoapply_folder_still_imports_on_its_own():
    """`python -c "import ..."` from inside backend/AutoApply still works."""
    result = subprocess.run(
        [sys.executable, "-c", "import AnswerBankManager, Onboarding, resumeRead"],
        cwd=autoapply_modules.AUTOAPPLY_DIR, capture_output=True, text=True, timeout=60,
        check=False)
    assert result.returncode == 0, result.stderr


# ----- the checks from the AutoApply folder's own tests.py -----

def test_read_resume_returns_its_lines():
    """resumeRead reads the example resume into sections of text lines."""
    resume = autoapply_modules.resumeRead.readResume(str(EXAMPLE_PDF))
    assert resume is not None and resume["Other"]
    assert all(isinstance(line, str) for lines in resume.values() for line in lines)


def test_onboarding_asks_the_first_two_questions(bank_file, monkeypatch):
    """Asking questions 0 and 1 for the test user saves both replies."""
    monkeypatch.setattr("builtins.input", lambda *args: "x")
    user_id = USER.getTestUserID()
    autoapply_modules.Onboarding.askQuestion(user_id, "0")
    autoapply_modules.Onboarding.askQuestion(user_id, "1")
    assert ABM.LoadUser(user_id) == {"Name": "x", "Age": "x"}


def test_saved_resume_sections_load_back_and_clear(bank_file):
    """A whole resume saved for the test user loads back by section, and clearing empties it."""
    user_id = USER.getTestUserID()
    resume = autoapply_modules.resumeRead.readResume(str(EXAMPLE_PDF))
    ABM.SaveResponseDictionary(user_id, resume)
    for header, lines in resume.items():
        assert ABM.LoadData(user_id, header) == lines
    ABM.ClearUser(user_id)
    assert ABM.LoadUser(user_id) == {}
