"""Applications: paste a link, list them, see what needs you (US5, US7, US11, US16)."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import NEEDS_YOU, QUEUED, SKIPPED, Application, User
from app.schemas import ApplicationIn, ApplicationOut
from app.services.ats import company_from_url, detect_ats

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(status: str | None = None, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Everything the student has applied to, newest first (US11)."""
    query = db.query(Application).filter(Application.user_id == user.id)
    if status:
        query = query.filter(Application.status == status)
    return query.order_by(Application.created_at.desc()).all()


@router.get("/needs-you", response_model=list[ApplicationOut])
def needs_you(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Applications waiting on the student (US7, US8)."""
    return list_applications(status=NEEDS_YOU, user=user, db=db)


@router.post("", response_model=ApplicationOut, status_code=201)
def apply_from_link(data: ApplicationIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Queue a job link for the agent (US5, UC5)."""
    url = data.url.strip()

    ats = detect_ats(url)
    if ats is None:
        raise HTTPException(400, "We only support Greenhouse, Lever and Ashby links right now.")

    already = db.query(Application).filter(
        Application.user_id == user.id, Application.url == url).first()
    if already:
        raise HTTPException(409, "You already applied to this posting.")

    # daily limit (US16). TODO: hold it for tomorrow instead of refusing.
    start_of_today = datetime.combine(date.today(), datetime.min.time())
    used_today = db.query(Application).filter(
        Application.user_id == user.id, Application.created_at >= start_of_today).count()
    if used_today >= user.daily_limit:
        raise HTTPException(429, f"Daily limit of {user.daily_limit} reached.")

    application = Application(user_id=user.id, url=url, ats=ats,
                              company=company_from_url(url), status=QUEUED)
    db.add(application)
    db.commit()
    return application


@router.post("/{app_id}/skip", response_model=ApplicationOut)
def skip_application(app_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Student decides not to finish a Needs you item (UC7 3a)."""
    application = db.get(Application, app_id)
    if application is None or application.user_id != user.id:
        raise HTTPException(404, "Application not found.")
    application.status = SKIPPED
    db.commit()
    return application

# TODO(US7): POST /{app_id}/answers so the student can answer Needs you questions
# and send the application back to the agent.
# TODO(US11): GET /export.csv for the tracker export.
