"""Turns a resume's `{header: [lines]}` sections into profile fields."""
import re

from server.resume.education import group_education
from server.resume.found_entries import (COURSEWORK_SUGGESTION, CUSTOM_SUGGESTION, FoundEntries,
                                         UnplacedText)
from server.resume.line_shapes import is_anchor
from server.resume.line_text import clean, split_label, unbullet
from server.resume.opening_lines import read_opening_lines
from server.resume.patterns import DEGREE_RE, SCHOOL_RE
from server.resume.profile_patch import ProfilePatch
from server.resume.projects import group_projects
from server.resume.roles import group_roles
from server.resume.section_kind import (ExperienceKind, SectionKind, classify_header,
                                        experience_kind, header_title)
from server.resume.skills import SPOKEN_RE, glue_skill_lines, is_prose
from server.resume.titles import title_word_count
from server.resume.wrapping import join_wrapped

# The lines before the first header come under this name
OPENING_SECTION = "Other"


def sections_to_profile(sections: dict[str, list[str]]) -> tuple[dict, list[dict], list[dict]]:
    """Return (profile patch, unplaced sections, parse labels) for a resume's sections.

    The patch holds the Profile fields that could be filled; each unplaced section is text that
    fits none of them; the labels are the ResumeParse `sections` lines, `{status, label}`.
    """
    found = FoundEntries()
    for header, lines in (sections or {}).items():
        lines = _join_lines(lines)
        if header == OPENING_SECTION:
            read_opening_lines(lines, found)
        elif lines:
            _SectionReader(found, header).read(lines)
    return ProfilePatch.build(found).to_json()


def _join_lines(lines: list[str] | None) -> list[str]:
    """Return the section's non-blank lines with wrapped lines joined back together."""
    return join_wrapped([line for line in (lines or []) if line and line.strip()])


class _SectionReader:  # pylint: disable=too-few-public-methods  # one reader per call, used through read()
    """Reads one headed section into a FoundEntries."""

    def __init__(self, found: FoundEntries, header: str):
        self.found = found
        self.header = header
        kind = classify_header(header)
        self.kind = kind
        self.role_kind = (experience_kind(header) if kind is SectionKind.EXPERIENCE
                          else ExperienceKind.WORK)

    def read(self, lines: list[str]) -> None:
        """Send the section's lines to the reader for its kind."""
        kind = self._settle_kind(lines)
        if kind is SectionKind.COURSEWORK:
            lines = self._split_off_schools(lines)
            if not lines:
                return
        if kind is SectionKind.CONTACT:
            for line in lines:
                self.found.contact.read(line)
        elif kind is SectionKind.EDUCATION:
            self.found.education_groups.extend(group_education(lines))
        elif kind is SectionKind.EXPERIENCE:
            self._read_roles(lines)
        elif kind is SectionKind.PROJECTS:
            self.found.project_groups.extend(group_projects(lines))
        elif kind is SectionKind.SKILLS:
            self._read_skills(lines)
        else:
            self._keep_unplaced(kind, lines)

    def _settle_kind(self, lines: list[str]) -> SectionKind:
        """Return the section's kind once its lines are known, not just its header."""
        kind = self.kind
        if self.role_kind is not ExperienceKind.WORK and not any(is_anchor(line)
                                                                for line in lines):
            kind = SectionKind.CUSTOM  # a list of clubs or awards with no dates isn't roles
        if kind is SectionKind.LANGUAGES:
            kind = SectionKind.CUSTOM if SPOKEN_RE.search(" ".join(lines)) else SectionKind.SKILLS
        if kind is SectionKind.SKILLS and is_prose(lines):
            kind = SectionKind.CUSTOM  # a functional resume's "Skills & Accomplishments"
        return kind

    def _split_off_schools(self, lines: list[str]) -> list[str]:
        """Read a school listed after "Relevant Coursework" as education; return the rest."""
        school_at = next((i for i, line in enumerate(lines) if SCHOOL_RE.search(line)), None)
        if school_at is None:
            return lines
        self.found.education_groups.extend(group_education(lines[school_at:]))
        return lines[:school_at]

    def _read_roles(self, lines: list[str]) -> None:
        """Add each role; a degree in a mixed timeline goes to education instead."""
        for group in group_roles(lines):
            head = [line for line in group if not line.startswith("• ")]
            # "2013  B.A., Marketing  /  2017  Marquette", but not "Master's Researcher" (a title)
            if any(DEGREE_RE.search(line) for line in head) and not title_word_count(
                    " ".join(head)):
                bullets = [line[2:] for line in group if line.startswith("• ")]
                self.found.education_groups.append((head + bullets, False))
            else:
                self.found.experience_groups.append((group, self.role_kind))

    def _read_skills(self, lines: list[str]) -> None:
        """Keep the skills lines; a list of spoken languages becomes a custom field instead."""
        self.found.has_skills_section = True
        for line in glue_skill_lines(lines):
            label, body = split_label(unbullet(line))
            if label and re.search(r"languages", label, re.I) and SPOKEN_RE.search(body):
                self.found.unplaced.append(UnplacedText(f"Languages: {body}", CUSTOM_SUGGESTION))
            else:
                self.found.skills_lines.append(line)

    def _keep_unplaced(self, kind: SectionKind, lines: list[str]) -> None:
        """Keep a section that fits no profile field as one unplaced text."""
        if kind is SectionKind.COURSEWORK:
            body = ", ".join(clean(item) for line in lines
                             for item in re.split(r"\s{3,}|\s*[✓•·▪◆]\s*", line)
                             if clean(item))
            suggestion = COURSEWORK_SUGGESTION
        else:
            body = "; ".join(re.sub(r"\s{2,}", " ", unbullet(line)) for line in lines)
            suggestion = CUSTOM_SUGGESTION
        self.found.unplaced.append(UnplacedText(f"{header_title(self.header)}: {body}",
                                                suggestion))
