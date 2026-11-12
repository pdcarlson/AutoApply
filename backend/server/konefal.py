"""The one place that loads the teammate's modules in backend/AutoApply/ (spec 2.4).

They are a flat folder meant to run as `python main.py` from inside it, with bare imports
(`import AnswerBankManager`). Rather than turning them into a package (which would break that),
the folder is *appended* to sys.path, so their `tests`, `main` and `User` never shadow anything.

Nothing else in server/ imports AnswerBankManager, Onboarding or resumeRead directly.

AnswerBankManager keeps its file path in a module global. Every server bank operation goes
through `bank_file(path)`, which holds `_PATH_LOCK` and points the global at that bank first, so
two apps (tests) can't write each other's files and nothing ever writes AutoApply/Bank.json.
"""
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

AUTOAPPLY_DIR = Path(__file__).resolve().parents[1] / "AutoApply"
if str(AUTOAPPLY_DIR) not in sys.path:
    sys.path.append(str(AUTOAPPLY_DIR))

# pylint: disable=wrong-import-position,import-error
import AnswerBankManager  # noqa: E402
import Onboarding  # noqa: E402
import resumeRead  # noqa: E402

BANK_FILE = "answer_bank.json"

_PATH_LOCK = threading.RLock()


def bank_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / BANK_FILE


def configure(data_dir: Path | str) -> Path:
    """Points AnswerBankManager at `<data_dir>/answer_bank.json`. Called from create_app."""
    path = bank_path(data_dir)
    with _PATH_LOCK:
        AnswerBankManager.setBankPath(str(path))
    return path


@contextmanager
def bank_file(path: Path | str) -> Iterator:
    """`with bank_file(p) as abm:` runs AnswerBankManager calls against the bank at `p`."""
    with _PATH_LOCK:
        AnswerBankManager.setBankPath(str(path))
        yield AnswerBankManager


def onboarding_questions() -> dict[str, list]:
    """OnboardingQuestions.json: id -> [prompt, bank key, category?]."""
    return Onboarding.loadQuestions()


def read_resume(path: Path | str) -> dict[str, list[str]] | None:
    """resumeRead.readResume: {header: [lines]} with "Other" first, or None if no text."""
    return resumeRead.readResume(str(path))


def page_count(path: Path | str) -> int | None:
    return resumeRead.pageCount(str(path))
