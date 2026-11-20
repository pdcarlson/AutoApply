"""Reads the Education section of a resume into EducationEntry objects."""
import re

from server.resume.dates import DATE, cut_dates, has_dates, read_dates
from server.resume.entries import EducationEntry
from server.resume.layout import split_line
from server.resume.line_shapes import is_anchor, is_head_like
from server.resume.line_text import clean, is_bullet, split_label, unbullet
from server.resume.patterns import COLUMNS_RE, DEGREE_RE, GPA_RE, SCHOOL_RE
from server.resume.places import as_place, strip_location


def parse_education(lines: list[str], school: str = "",
                    location: str = "") -> tuple[EducationEntry, list[str]]:
    """Read one degree's lines into (EducationEntry, the lines it couldn't use).

    `school` and `location` are given for a further degree listed under the previous entry's
    school; the lines then aren't searched for a school.
    """
    return _EducationReader(lines, school, location).read()


class _EducationReader:  # pylint: disable=too-few-public-methods  # one reader per call, used through read()
    """Reads one degree's lines, filling one EducationEntry."""

    def __init__(self, lines: list[str], school: str, location: str):
        self.lines = lines
        self.entry = EducationEntry(school=school)
        self.fallback_location = location
        self.leftovers: list[str] = []
        self.date_texts: list[str] = []
        # "M.S., Statistics" then "University of Washington": the school is the line naming one
        self.school_line = next((i for i, line in enumerate(lines) if SCHOOL_RE.search(line)), 0)

    def read(self) -> tuple[EducationEntry, list[str]]:
        """Return the filled entry and the leftover lines."""
        for index, raw in enumerate(self.lines):
            self._read_line(index, unbullet(raw))
        entry = self.entry
        if self.date_texts:
            found = read_dates(" ".join(self.date_texts))
            entry.start, entry.end = found.start, found.end
        if not entry.location and entry.school:
            entry.school, entry.location = strip_location(entry.school)
        entry.location = entry.location or self.fallback_location
        return entry, self.leftovers

    def _read_line(self, index: int, line: str) -> None:
        """Take what one line says about the degree; keep it as a leftover if nothing."""
        label, body = split_label(line)
        if label and re.search(r"coursework", label, re.I):
            self.entry.coursework = ", ".join(filter(None, [self.entry.coursework, body]))
            return
        line, places = self._take_places(line)
        text, dates, place = split_line(line)
        if dates:
            self.date_texts.append(dates)
        if place and not self.entry.location:
            self.entry.location = place
        used = bool(dates or place or places)
        used = self._take_gpa(text) or used
        used = self._take_degree(text) or used
        used = self._take_school(index, text) or used
        if not dates:
            found, rest = cut_dates(text)
            if found and not label:
                self.date_texts.append(found)
                used = used or not rest or rest == self.entry.school
        if not used and text:
            self.leftovers.append(line)

    def _take_places(self, line: str) -> tuple[str, list[str]]:
        """Take the places out of "University of Central Florida · Orlando, FL · May 2020"."""
        pieces = re.split(r"\s+[·•|]\s+", line)
        places = [piece for piece in pieces if as_place(piece) and as_place(piece) != "Remote"]
        if places:
            if not self.entry.location:
                self.entry.location = as_place(places[0])
            line = " · ".join(piece for piece in pieces if piece not in places)
        return line, places

    def _take_gpa(self, text: str) -> bool:
        """Take the GPA from the text; True if it was the first one found."""
        gpa = GPA_RE.search(text)
        if not gpa or self.entry.gpa:
            return False
        self.entry.gpa = gpa.group(1)
        return True

    def _take_degree(self, text: str) -> bool:
        """Take the degree and the major after it; True if it was the first degree found."""
        degree = DEGREE_RE.search(text)
        if not degree or self.entry.degree_type:
            return False
        self.entry.degree_type = degree.group(0).strip()
        self.entry.major = _major_after(text, degree.end())
        return True

    def _take_school(self, index: int, text: str) -> bool:
        """Take the school from its line; True if one was found."""
        if self.entry.school or not (index == self.school_line or SCHOOL_RE.search(text)):
            return False
        parts = [part for part in re.split(r"\s+[-–—|·]\s+|,\s*", text) if part.strip()]
        school = next((part for part in parts if SCHOOL_RE.search(part)), None)
        if school is None:
            # "ATD Certificate, Instructional Design — Association for Talent Development"
            dashed = re.split(r"\s+[-–—]\s+", text)
            candidates = ([dashed[-1]] if len(dashed) > 1 else []) + parts
            school = next((part for part in candidates if not DEGREE_RE.search(part)
                           and not GPA_RE.search(part) and not has_dates(part)), "")
        self.entry.school = clean(re.sub(r"\([^)]*\)", "", school))
        return bool(self.entry.school)


def _major_after(text: str, degree_end: int) -> str:
    """Return the major written after the degree ("B.S. Computer Science, 2027" -> "Computer
    Science"), or "" when what follows is a school."""
    after = re.sub(r"^\s*(?:Candidate\b)?[\s,]*(?:(?:in|of)\s+)?", "", text[degree_end:].strip())
    if re.match(r"\s*[-–—]\s", text[degree_end:]):
        after = ""  # "M.Arch — ETH Zürich": the dash brings the school, not a major
    after = re.split(r"\s*[,|(;·]\s*|\s+[-–—]\s+|\s+GPA\b", after, maxsplit=1)[0]
    after = re.split(DATE, after, maxsplit=1, flags=re.I)[0]
    return "" if SCHOOL_RE.search(after) else clean(after)


def group_education(lines: list[str]) -> list[tuple[list[str], bool]]:
    """Split an Education section into [(lines, same_school)], one entry per degree.

    A second degree line under one school ("Master of ..." then "Bachelor of ...") starts a new
    entry with `same_school` True: it takes its school from the entry before it.
    """
    groups: list[tuple[list[str], bool]] = []
    for line in lines:
        if not groups:
            groups.append(([line], False))
            continue
        group = groups[-1][0]
        if is_bullet(line) or line.strip().startswith("("):
            group.append(line)  # a bullet, or "(MPP)" under "Master of Public Policy"
        elif (SCHOOL_RE.search(line) and is_head_like(line)
              and any(SCHOOL_RE.search(earlier) for earlier in group)):
            groups.append(([line], False))
        elif DEGREE_RE.search(line) and any(DEGREE_RE.search(earlier) for earlier in group):
            groups.append(([line], True))
        elif _starts_new_degree(line, group):
            groups.append(([line], False))
        else:
            group.append(line)
    return groups


def _starts_new_degree(line: str, group: list[str]) -> bool:
    """Return True for one line per degree, each with its own date column."""
    return is_anchor(line) and any(is_anchor(earlier) for earlier in group) and bool(
        DEGREE_RE.search(line) or SCHOOL_RE.search(line) or COLUMNS_RE.search(line.strip()))
