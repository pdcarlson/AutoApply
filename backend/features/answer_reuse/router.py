"""Answer reuse routes (US9).

- POST /api/answers/remember: save a student's answer without making a
  duplicate when the same question was answered before (the Needs you
  "Save to answer bank" box).
- GET /api/answers/match?question=...: the saved answer for a question, if any
  (the "you have answered this before" hint on Needs you).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import AnswerIn, AnswerOut
from features.answer_reuse.service import AnswerReuse

router = APIRouter(prefix="/api/answers", tags=["answers"])


@router.post("/remember", response_model=AnswerOut)
def remember_answer(data: AnswerIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    try:
        return AnswerReuse(db, user.id).remember(data.question, data.answer)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err


@router.get("/match", response_model=AnswerOut | None)
def match_answer(question: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return AnswerReuse(db, user.id).find(question)
