"""Request bodies for the setup and profile routes."""
# pylint: disable=invalid-name  # field names are the API's camelCase JSON keys
# pylint: disable=duplicate-code  # the bodies mirror the resume entries' JSON on purpose
from typing import Literal

from pydantic import BaseModel


class ProfileLinkBody(BaseModel):
    """One ProfileLink."""

    id: str
    label: str = ""
    url: str = ""
    fixed: bool = False


class CustomFieldBody(BaseModel):
    """One CustomField."""

    id: str
    label: str = ""
    value: str = ""


class EducationBody(BaseModel):
    """One Education entry."""

    id: str
    school: str = ""
    degreeType: str = ""
    major: str = ""
    gpa: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    coursework: str = ""


ExperienceKind = Literal["work", "leadership", "volunteer", "activity"]


class ExperienceBody(BaseModel):
    """One Experience entry."""

    id: str
    kind: ExperienceKind = "work"
    title: str = ""
    org: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    current: bool = False
    detail: str = ""


class ProjectBody(BaseModel):
    """One Project entry."""

    id: str
    name: str = ""
    tech: str = ""
    detail: str = ""


class ProfileUpdateBody(BaseModel):
    """ProfileUpdate: every Profile field but resume and unplaced. Only the keys sent change."""

    firstName: str = ""
    middleName: str = ""
    lastName: str = ""
    email: str = ""
    phone: str = ""
    street: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = ""
    links: list[ProfileLinkBody] = []
    education: list[EducationBody] = []
    experience: list[ExperienceBody] = []
    projects: list[ProjectBody] = []
    skills: list[str] = []
    custom: list[CustomFieldBody] = []


class UnplacedActionBody(BaseModel):
    """What to do with one unplaced resume section."""

    action: Literal["accept", "dismiss"]


CommonQuestionKey = Literal["workAuthorized", "needsSponsorship", "graduation", "earliestStart",
                            "relocate", "locations", "expectedPay", "familyEmployers", "gender",
                            "hispanicLatino", "race", "veteran", "disability"]
Decline = Literal["decline"]


class CommonAnswersBody(BaseModel):
    """CommonAnswers: setup's answers to the questions most forms ask."""

    workAuthorized: Literal["Yes", "No"] | None = None
    needsSponsorship: Literal["Yes", "No"] | None = None
    graduation: str | None = None
    earliestStart: str | None = None
    relocate: Literal["Yes", "No", "Depends"] | None = None
    locations: list[str] = []
    expectedPay: str = ""
    familyEmployers: list[str] = []
    # Voluntary self-ID (server/self_id.py): a value, "decline", or None when not answered yet
    gender: Literal["Male", "Female", "Non-binary"] | Decline | None = None
    hispanicLatino: Literal["Yes", "No"] | Decline | None = None
    race: Literal["American Indian or Alaska Native", "Asian", "Black or African American",
                  "Native Hawaiian or Other Pacific Islander", "White",
                  "Two or More Races"] | Decline | None = None
    veteran: Literal["Yes", "No"] | Decline | None = None
    disability: Literal["Yes", "No"] | Decline | None = None
    skipped: list[CommonQuestionKey] = []


class JobPreferencesBody(BaseModel):
    """JobPreferences: the kinds of roles the person wants."""

    roleTypes: list[str]
    fullTime: bool
    internship: bool
