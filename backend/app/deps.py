"""Shared FastAPI dependencies."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Profile, User

DEMO_EMAIL = "demo@autoapply.local"


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Return the signed-in user.

    TODO(US1): replace with real Google sign in. For now every request acts as
    one demo user so the rest of the app can be built and tested.
    Once real sessions exist, every route already filters by this user, which
    covers SE1 (users only see their own data).
    """
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            name="Demo Student",
            confidence_threshold=settings.default_confidence_threshold,
            daily_limit=settings.default_daily_limit,
        )
        user.profile = Profile()
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
