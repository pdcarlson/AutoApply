"""Exact-match answer reuse (US9, F9).

Once the student answers a question, the agent uses that answer the next time
the identical question shows up instead of asking again. "Identical" means the
same words once case, spacing, curly quotes, a trailing "?" or ":" and the
required-field asterisk are ignored. Reworded questions ("Do you need
sponsorship?" vs "Will you require visa sponsorship?") are F10, a later Should.

Answers live in the answer bank table (app.models.Answer), so anything saved
from the Answer Bank screen is reused here, and the other way round.

How the agent uses this, once a fill loop exists (US6):

    reused = AnswerReuse(db, user_id).reuse(question_label)
    if reused:
        fill the field with reused.text  # confidence 100, source for the S3 log
    else:
        ask the student (US7), then AnswerReuse(db, user_id).remember(question, answer)
"""
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Answer

_EDGE_CHARS = " *:?."
_TAGS = re.compile(r"\((required|optional)\)")


def normalize_question(text: str) -> str:
    """The form of a question two forms have to share to count as identical."""
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    text = _TAGS.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(_EDGE_CHARS)


@dataclass(frozen=True)
class ReusedAnswer:
    """A saved answer the agent can fill in without asking."""

    answer_id: int
    text: str
    confidence: int = 100  # an exact match always clears the US7 threshold

    @property
    def source(self) -> str:
        """Where the value came from, for the fill log (S3)."""
        return f"answer bank #{self.answer_id}"


class AnswerReuse:
    """One student's answer bank, looked up by exact question."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def find(self, question: str) -> Answer | None:
        """The saved answer for this question, newest first if there are duplicates."""
        key = normalize_question(question)
        if not key:
            return None
        answers = (self.db.query(Answer)
                   .filter(Answer.user_id == self.user_id)
                   .order_by(Answer.id.desc())
                   .all())
        return next((a for a in answers if normalize_question(a.question) == key), None)

    def reuse(self, question: str) -> ReusedAnswer | None:
        """Use a saved answer, counting the use for the Answer Bank screen."""
        answer = self.find(question)
        if answer is None:
            return None
        answer.times_used = (answer.times_used or 0) + 1
        self.db.commit()
        return ReusedAnswer(answer.id, answer.answer)

    def remember(self, question: str, answer_text: str) -> Answer:
        """Save what the student answered, updating the old answer if they'd been asked before."""
        if not normalize_question(question) or not answer_text.strip():
            raise ValueError("Both the question and the answer need some text.")
        answer = self.find(question)
        if answer is None:
            answer = Answer(user_id=self.user_id, question=question.strip())
            self.db.add(answer)
        answer.answer = answer_text.strip()
        self.db.commit()
        return answer
