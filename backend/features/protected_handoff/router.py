"""Finishing a protected step (US8, UC4).

When the agent hands a CAPTCHA, sign-in or SSN step to the student, the
application waits in Needs you. Once the student has dealt with it on the
employer's site, they tell us how it went:

- submitted: they finished the whole application there, so it's marked submitted.
- retry: the step is out of the way (say, a login they've now set up), so the
  application goes back in the queue for the agent.
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import NEEDS_YOU, QUEUED, SUBMITTED, Application, User
from app.schemas import ApplicationOut

router = APIRouter(prefix="/api/applications", tags=["applications"])


class HandoffDoneIn(BaseModel):
    outcome: Literal["submitted", "retry"]


@router.post("/{app_id}/handoff-done", response_model=ApplicationOut)
def handoff_done(app_id: int, data: HandoffDoneIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    application = db.get(Application, app_id)
    if application is None or application.user_id != user.id:
        raise HTTPException(404, "Application not found.")
    if application.status != NEEDS_YOU:
        raise HTTPException(409, "This application isn't waiting on you.")

    if data.outcome == "submitted":
        application.status = SUBMITTED
        application.submitted_at = datetime.now()
        application.reason = "You finished this one on the employer's site."
    else:
        application.status = QUEUED
        application.reason = ""
    db.commit()
    return application
