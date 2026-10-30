"""Database tables.

Four tables cover the Must path: a user, their profile, their saved answers,
and the applications the agent works on.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Application statuses, in the order an application usually moves through them.
QUEUED = "queued"
IN_PROGRESS = "in_progress"
NEEDS_YOU = "needs_you"  # US7, US8
SUBMITTED = "submitted"
FAILED = "failed"
SKIPPED = "skipped"


class User(Base):
    """One student. Created on first Google sign in (US1)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    confidence_threshold: Mapped[int] = mapped_column(Integer, default=90)  # US7
    daily_limit: Mapped[int] = mapped_column(Integer, default=25)  # US16
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # cascade so deleting a user removes everything about them (US17)
    profile: Mapped["Profile"] = relationship(back_populates="user", cascade="all, delete-orphan")
    answers: Mapped[list["Answer"]] = relationship(cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(cascade="all, delete-orphan")


class Profile(Base):
    """Facts pulled from the resume and confirmed by the student (US2, US3).

    The agent only fills forms from this table and the answer bank (US13).
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    school: Mapped[str] = mapped_column(String(255), default="")
    degree: Mapped[str] = mapped_column(String(255), default="")
    grad_date: Mapped[str] = mapped_column(String(50), default="")
    # list of {"title", "company", "dates"}
    experience: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    # names of fields the parser was unsure about, shown dashed in the UI (US3)
    flagged_fields: Mapped[list] = mapped_column(JSON, default=list)
    resume_path: Mapped[str] = mapped_column(String(500), default="")
    confirmed: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(back_populates="profile")


class Answer(Base):
    """A saved answer to an application question (US4, US9, US10)."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    times_used: Mapped[int] = mapped_column(Integer, default=0)


class Application(Base):
    """One job the student asked the agent to apply to (US5, US6, US11)."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    url: Mapped[str] = mapped_column(String(1000))
    ats: Mapped[str] = mapped_column(String(20))  # greenhouse / lever / ashby
    company: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default=QUEUED)
    # why it's in Needs you or Failed, shown to the student in plain words (U2)
    reason: Mapped[str] = mapped_column(Text, default="")
    screenshot_path: Mapped[str] = mapped_column(String(500), default="")  # US12
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
