"""Answer bank (US4, US9, US10)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Answer, User
from app.schemas import AnswerIn, AnswerOut

router = APIRouter(prefix="/api/answers", tags=["answers"])


def _get_own_answer(answer_id: int, user: User, db: Session) -> Answer:
    answer = db.get(Answer, answer_id)
    if answer is None or answer.user_id != user.id:
        raise HTTPException(404, "Answer not found.")
    return answer


@router.get("", response_model=list[AnswerOut])
def list_answers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Answer).filter(Answer.user_id == user.id).order_by(Answer.id).all()


@router.post("", response_model=AnswerOut, status_code=201)
def create_answer(data: AnswerIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    answer = Answer(user_id=user.id, question=data.question.strip(), answer=data.answer.strip())
    db.add(answer)
    db.commit()
    return answer


@router.put("/{answer_id}", response_model=AnswerOut)
def update_answer(answer_id: int, data: AnswerIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    answer = _get_own_answer(answer_id, user, db)
    answer.question = data.question.strip()
    answer.answer = data.answer.strip()
    db.commit()
    return answer


@router.delete("/{answer_id}", status_code=204)
def delete_answer(answer_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    db.delete(_get_own_answer(answer_id, user, db))
    db.commit()
