"""Works out what a resume section holds from its header."""
import re
from enum import Enum


class SectionKind(str, Enum):
    """What a resume section holds, and so where its lines go in the profile."""

    CONTACT = "contact"
    COURSEWORK = "coursework"
    EDUCATION = "education"
    PROJECTS = "projects"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    LANGUAGES = "languages"
    CUSTOM = "custom"


class ExperienceKind(str, Enum):
    """The kind of an Experience entry, as the profile stores it."""

    WORK = "work"
    LEADERSHIP = "leadership"
    VOLUNTEER = "volunteer"
    ACTIVITY = "activity"


# Header words for sections shaped like jobs (title, organization, dates, bullets) that aren't
# work, and the Experience kind each gives. "Leadership Experience" is a leadership entry.
EXPERIENCE_KIND_WORDS = {
    "Leadership": ExperienceKind.LEADERSHIP, "Volunteer": ExperienceKind.VOLUNTEER,
    "Volunteering": ExperienceKind.VOLUNTEER, "Community": ExperienceKind.VOLUNTEER,
    "Activities": ExperienceKind.ACTIVITY, "Involvement": ExperienceKind.ACTIVITY,
}
_EXPERIENCE_WORDS = {"experience", "experiences", "employment", "career", "timeline"}
_SKILLS_WORDS = {"skills", "competencies", "expertise", "proficiencies", "technologies", "tools",
                 "toolkit", "software", "stack"}


def classify_header(header: str) -> SectionKind:
    """Return the SectionKind a header names; CUSTOM when it names none."""
    words = {word.lower() for word in re.findall(r"[A-Za-z]+", header)}
    for kind, names_kind in _HEADER_RULES:
        if names_kind(words):
            return kind
    return SectionKind.CUSTOM


def _names_experience(words: set[str]) -> bool:
    """Return True when the header's words name a section of roles."""
    return bool(words & _EXPERIENCE_WORDS or {"work", "history"} <= words
                or any(word.title() in EXPERIENCE_KIND_WORDS for word in words))


# Checked in order: "Relevant Coursework" is coursework even under an Education header
_HEADER_RULES = [
    (SectionKind.CONTACT, lambda words: "contact" in words),
    (SectionKind.COURSEWORK, lambda words: bool(words & {"relevant", "coursework"})),
    (SectionKind.EDUCATION, lambda words: "education" in words),
    (SectionKind.PROJECTS, lambda words: bool(words & {"projects", "project"})),
    (SectionKind.EXPERIENCE, _names_experience),
    (SectionKind.SKILLS, lambda words: bool(words & _SKILLS_WORDS)),
    (SectionKind.LANGUAGES, lambda words: "languages" in words),
]


def experience_kind(header: str) -> ExperienceKind:
    """Return the ExperienceKind of an Experience-type header; WORK by default."""
    for word in header.split():
        word = word.strip(":,.&").title()
        if word in EXPERIENCE_KIND_WORDS:
            return EXPERIENCE_KIND_WORDS[word]
    return ExperienceKind.WORK


def header_title(header: str) -> str:
    """Return the header as a label: no trailing colon, and Title Case if it was UPPER CASE."""
    header = header.strip().rstrip(":").strip()
    return header.title() if header.isupper() else header
