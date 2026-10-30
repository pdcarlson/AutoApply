"""Profile and resume upload (US2, US3)."""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])

ALLOWED_TYPES = {".pdf", ".docx"}


@router.get("", response_model=ProfileOut)
def read_profile(user: User = Depends(get_current_user)):
    return user.profile


@router.put("", response_model=ProfileOut)
def update_profile(data: ProfileIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Save edits from the profile screen (US3)."""
    profile = user.profile
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    # once the student has looked at it, nothing is a "guess" anymore
    if data.confirmed:
        profile.flagged_fields = []
    db.commit()
    return profile


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(file: UploadFile, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Store the resume file (F2).

    TODO(US2): send the text to the parser and fill in the profile fields,
    adding any low-confidence ones to profile.flagged_fields.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, "Resume must be a PDF or DOCX file.")

    contents = await file.read()
    if len(contents) > settings.max_resume_mb * 1024 * 1024:
        raise HTTPException(400, f"Resume must be under {settings.max_resume_mb} MB.")

    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as out:
        out.write(contents)

    user.profile.resume_path = path
    db.commit()
    return user.profile
