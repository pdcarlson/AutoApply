"""Loads the onboarding question catalog."""
import json
from pathlib import Path

QUESTIONS_PATH = Path(__file__).resolve().with_name("onboarding_questions.json")


def load_questions() -> dict[str, list]:
    """Return question id -> [prompt, bank key], with the Answer-bank category third if set."""
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
