"""Shapes of the JSON going in and out of the API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    confidence_threshold: int
    daily_limit: int


class SettingsIn(BaseModel):
    confidence_threshold: int | None = None
    daily_limit: int | None = None


class ProfileBase(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    school: str = ""
    degree: str = ""
    grad_date: str = ""
    experience: list[dict] = []
    skills: list[str] = []


class ProfileIn(ProfileBase):
    confirmed: bool = False


class ProfileOut(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    flagged_fields: list[str] = []
    resume_path: str = ""
    confirmed: bool = False


class AnswerIn(BaseModel):
    question: str
    answer: str


class AnswerOut(AnswerIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    times_used: int


class ApplicationIn(BaseModel):
    url: str


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    ats: str
    company: str
    role: str
    status: str
    reason: str
    screenshot_path: str
    created_at: datetime | None = None
    submitted_at: datetime | None = None
