"""The profile fields read from a resume, and the labels that report what was found."""
from dataclasses import dataclass

from server.resume.contact import Contact
from server.resume.education import parse_education
from server.resume.entries import EducationEntry, ExperienceEntry, ProjectEntry
from server.resume.experience import parse_experience
from server.resume.found_entries import COURSEWORK_SUGGESTION, FoundEntries, UnplacedText
from server.resume.patterns import SCHOOL_RE
from server.resume.projects import parse_project
from server.resume.skills import parse_skills, skills_from_projects


def _plural(count: int, one: str, many: str) -> str:
    """Return "1 role" or "3 roles"."""
    return f"{count} {one if count == 1 else many}"


def _label(status: str, text: str) -> dict:
    """Return one ResumeParse `sections` line."""
    return {"status": status, "label": text}


@dataclass
class ProfilePatch:  # pylint: disable=too-many-instance-attributes  # one field per profile area
    """Everything a resume filled in, with the text that fit nowhere."""

    contact: Contact
    education: list[EducationEntry]
    experience: list[ExperienceEntry]
    projects: list[ProjectEntry]
    skills: list[str]
    unplaced: list[UnplacedText]
    has_skills_section: bool

    @classmethod
    def build(cls, found: FoundEntries) -> "ProfilePatch":
        """Parse each entry's lines found in a resume."""
        unplaced = list(found.unplaced)
        education = _parse_degrees(found.education_groups, unplaced)
        experience = [parse_experience(group, kind) for group, kind in found.experience_groups]
        projects = [parse_project(group) for group in found.project_groups]
        skills = (parse_skills(found.skills_lines) if found.has_skills_section
                  else skills_from_projects(projects))
        return cls(found.contact, education, experience, projects, skills, unplaced,
                   found.has_skills_section)

    def to_json(self) -> tuple[dict, list[dict], list[dict]]:
        """Return (Profile fields, UnplacedSections, ResumeParse labels) in the API's JSON."""
        patch = self.contact.to_json()
        patch.update(
            education=[entry.to_json(f"ed-{n}") for n, entry in enumerate(self.education, 1)],
            experience=[entry.to_json(f"x-{n}") for n, entry in enumerate(self.experience, 1)],
            projects=[entry.to_json(f"p-{n}") for n, entry in enumerate(self.projects, 1)],
            skills=self.skills)
        unplaced = [text.to_json(f"un-{n}") for n, text in enumerate(self.unplaced, 1)]
        return patch, unplaced, self._labels()

    def _labels(self) -> list[dict]:
        """Return one label per kind of thing found, warning where something is missing."""
        contact_fields = _plural(self.contact.count(), "field", "fields")
        labels = [_label("ok", f"Contact info · {contact_fields}")]
        if self.education:
            school = self.education[0].school or len(self.education)
            labels.append(_label("ok", f"Education · {school}"))
        if self.experience:
            roles = _plural(len(self.experience), "role", "roles")
            labels.append(_label("ok", f"Experience · {roles}"))
        if self.projects:
            labels.append(_label("ok", f"Projects · {len(self.projects)}"))
        labels.append(_label("ok" if self.has_skills_section and self.skills else "warn",
                             f"Skills · {len(self.skills)}"))
        if self.unplaced:
            sections = _plural(len(self.unplaced), "section", "sections")
            labels.append(_label("warn", f"{sections} we couldn’t place"))
        return labels


def _parse_degrees(groups: list[tuple[list[str], bool]],
                   unplaced: list[UnplacedText]) -> list[EducationEntry]:
    """Parse each degree; a degree under the previous one's school takes that school."""
    education: list[EducationEntry] = []
    for group, same_school in groups:
        if same_school and education and not any(SCHOOL_RE.search(line) for line in group):
            entry, leftovers = parse_education(group, education[-1].school,
                                               education[-1].location)
        else:
            entry, leftovers = parse_education(group)
        education.append(entry)
        unplaced.extend(UnplacedText(line, COURSEWORK_SUGGESTION) for line in leftovers)
    return education
