"""An answer the applicant already gave, and how questions are matched to it."""
from dataclasses import dataclass


def normalize(question: str) -> str:
    """Lowercase a question and drop extra spaces so the same question always matches."""
    return " ".join(question.lower().split()).rstrip("*").strip()


@dataclass
class SavedAnswer:
    """An answer the applicant already gave to a form question."""

    question: str
    answer: str

    def answers(self, question: str) -> bool:
        """Return True if this is the answer to that question, however it's spaced or cased."""
        return normalize(self.question) == normalize(question)
