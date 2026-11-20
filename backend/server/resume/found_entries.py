"""What has been read from a resume so far, before each entry's lines are parsed."""
from dataclasses import dataclass, field

from server.resume.contact import Contact
from server.resume.section_kind import ExperienceKind

COURSEWORK_SUGGESTION = "Add to Education"
CUSTOM_SUGGESTION = "Add as a custom field"


@dataclass
class UnplacedText:
    """Resume text that fits no profile field; header sections keep "<Header>: " in front."""

    text: str
    suggestion: str | None = None

    def to_json(self, section_id: str) -> dict:
        """Return the API UnplacedSection with this id."""
        return {"id": section_id, "text": self.text, "suggestion": self.suggestion}


@dataclass
class FoundEntries:
    """The contact details and the lines of each entry found in a resume, in order."""

    contact: Contact = field(default_factory=Contact)
    # (lines, same_school): a degree that takes its school from the one before it
    education_groups: list[tuple[list[str], bool]] = field(default_factory=list)
    experience_groups: list[tuple[list[str], ExperienceKind]] = field(default_factory=list)
    project_groups: list[list[str]] = field(default_factory=list)
    skills_lines: list[str] = field(default_factory=list)
    has_skills_section: bool = False
    unplaced: list[UnplacedText] = field(default_factory=list)
