"""Loads the answer bank, onboarding and resume modules from backend/onboarding/."""
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ONBOARDING_DIR = Path(__file__).resolve().parents[1] / "onboarding"
# The folder is a flat set of scripts with bare imports (`import AnswerBankManager`).
# Appending it to sys.path (rather than making it a package) keeps those working, and its
# `User` never shadows anything of ours.
if str(ONBOARDING_DIR) not in sys.path:
    sys.path.append(str(ONBOARDING_DIR))

# pylint: disable=wrong-import-position,wrong-import-order,import-error  # loaded from the folder appended above
import AnswerBankManager  # noqa: E402
import Onboarding  # noqa: E402
import resumeRead  # noqa: E402

BANK_FILE = "answer_bank.json"

# AnswerBankManager keeps its file path in a module global, so every bank operation holds this
# lock and points the global at its own bank first: two apps can't write each other's files.
_PATH_LOCK = threading.RLock()


def bank_path(data_dir: Path | str) -> Path:
    """Return where a data folder's answer bank file lives."""
    return Path(data_dir) / BANK_FILE


def configure(data_dir: Path | str) -> Path:
    """Point AnswerBankManager at `<data_dir>/answer_bank.json` and return that path."""
    path = bank_path(data_dir)
    with _PATH_LOCK:
        AnswerBankManager.setBankPath(str(path))
    return path


@contextmanager
def bank_file(path: Path | str) -> Iterator:
    """Run the AnswerBankManager calls inside `with bank_file(path) as manager:` on that file."""
    with _PATH_LOCK:
        AnswerBankManager.setBankPath(str(path))
        yield AnswerBankManager


def onboarding_questions() -> dict[str, list]:
    """Return OnboardingQuestions.json: id -> [prompt, bank key, category?]."""
    return Onboarding.loadQuestions()


def read_resume(path: Path | str) -> dict[str, list[str]] | None:
    """Return resumeRead's `{header: [lines]}` with "Other" first, or None if there's no text."""
    return resumeRead.readResume(str(path))


def page_count(path: Path | str) -> int | None:
    """Return how many pages the resume file has, or None when it can't tell."""
    return resumeRead.pageCount(str(path))
