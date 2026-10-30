"""The signed-in user and their settings (US1, US7, US16, US17)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import SettingsIn, UserOut

router = APIRouter(prefix="/api", tags=["user"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me/settings", response_model=UserOut)
def update_settings(data: SettingsIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Change the confidence threshold (US7) or daily limit (US16)."""
    if data.confidence_threshold is not None:
        user.confidence_threshold = max(0, min(100, data.confidence_threshold))
    if data.daily_limit is not None:
        user.daily_limit = max(1, data.daily_limit)
    db.commit()
    return user


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete the account and everything tied to it (US17).

    TODO(US17): also delete the resume file and screenshots from disk.
    """
    db.delete(user)
    db.commit()
