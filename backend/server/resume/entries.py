"""The profile entries a resume fills: education, experience and projects."""
from dataclasses import dataclass

from server.resume.section_kind import ExperienceKind


@dataclass
class EducationEntry:  # pylint: disable=too-many-instance-attributes  # one field per form field
    """One degree, as the profile's Education list holds it."""

    school: str = ""
    degree_type: str = ""
    major: str = ""
    gpa: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    coursework: str = ""

    def to_json(self, entry_id: str) -> dict:
        """Return the API Education with this id."""
        return {"id": entry_id, "school": self.school, "degreeType": self.degree_type,
                "major": self.major, "gpa": self.gpa, "location": self.location,
                "start": self.start, "end": self.end, "coursework": self.coursework}


@dataclass
class ExperienceEntry:  # pylint: disable=too-many-instance-attributes  # one field per form field
    """One role, as the profile's Experience list holds it."""

    kind: ExperienceKind = ExperienceKind.WORK
    title: str = ""
    org: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    current: bool = False
    detail: str = ""

    def to_json(self, entry_id: str) -> dict:
        """Return the API Experience with this id."""
        return {"id": entry_id, "kind": ExperienceKind(self.kind).value, "title": self.title,
                "org": self.org, "location": self.location, "start": self.start,
                "end": self.end, "current": self.current, "detail": self.detail}


@dataclass
class ProjectEntry:
    """One project, as the profile's Projects list holds it."""

    name: str = ""
    tech: str = ""
    detail: str = ""

    def to_json(self, entry_id: str) -> dict:
        """Return the API Project with this id."""
        return {"id": entry_id, "name": self.name, "tech": self.tech, "detail": self.detail}
