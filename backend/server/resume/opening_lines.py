"""Reads the lines before a resume's first header: the name, contact details and any entries."""
import re

from server.resume.contact import is_contact_item, is_contact_line, is_name, name_text, segments
from server.resume.dates import RANGE_RE
from server.resume.found_entries import FoundEntries, UnplacedText
from server.resume.layout import split_columns
from server.resume.line_text import clean, is_bullet, unbullet
from server.resume.patterns import (ADDRESS_RE, COLUMNS_RE, DEGREE_RE, NAME_WORD_RE, PROJECT_RE,
                                    SCHOOL_RE)
from server.resume.section_kind import ExperienceKind, SectionKind

# "BSN, RN, CCRN" beside the name
_CREDENTIALS_LINE_RE = re.compile(
    r"(?:[A-Z]{2,5}|(?:[A-Z]\.)+)(?:,\s*(?:[A-Z]{2,5}|(?:[A-Z]\.)+))+")
# A one-word name is joined with a last name found within this many lines of the top
_SPLIT_NAME_LINES = 6


def read_opening_lines(lines: list[str], found: FoundEntries) -> None:
    """Add what the lines before the first header say to `found`."""
    _OpeningLinesReader(found).read(lines)


def _classify_line(line: str) -> SectionKind | None:
    """Return the kind of entry a line starts, or None for text that fits nowhere."""
    has_range = bool(RANGE_RE.search(line))
    if DEGREE_RE.search(line):
        return SectionKind.EDUCATION
    if SCHOOL_RE.search(line) and not has_range:
        return SectionKind.EDUCATION
    if has_range:
        return SectionKind.EXPERIENCE
    if PROJECT_RE.match(COLUMNS_RE.split(line.strip())[0]):
        return SectionKind.PROJECTS
    return None


def _is_noise(line: str) -> bool:
    """Return True for lines that say nothing: "PR" (a monogram), "$14.2M   131%   3×"."""
    text = line.strip()
    letters = len(re.findall(r"[A-Za-z]", text))
    return len(text) <= 3 or letters < 0.35 * len(text.replace(" ", ""))


class _OpeningLinesReader:  # pylint: disable=too-few-public-methods  # one reader per call, used through read()
    """Reads the opening lines one by one into a FoundEntries."""

    def __init__(self, found: FoundEntries):
        self.found = found
        self.contact = found.contact
        self.current: list[str] | None = None  # the lines of the entry being read
        self.entries_started = False
        self.first_name = ""  # "Lukas" then "Brenner." on a later line

    def read(self, lines: list[str]) -> None:
        """Read every line, then settle for a one-word name if no full one turned up."""
        for index, line in enumerate(lines):
            self._read_line(index, line)
        if self.first_name and not self.contact.name:
            self.contact.name = self.first_name

    def _read_line(self, index: int, line: str) -> None:
        """Read one line as part of an entry, the name, contact details or loose text."""
        if self.current is not None and is_bullet(line):
            self.current.append(line)
            return
        if not self.entries_started:
            line = self._read_top_line(index, line)
            if line is None:
                return
        if is_contact_line(line, early=not self.entries_started):
            self.contact.read(line)
            return
        if _is_noise(line) or self._is_credentials(line):
            return
        self._add_entry_or_text(line)

    def _read_top_line(self, index: int, line: str) -> str | None:
        """Take contact details and the name from a line above the entries.

        Returns what's left of the line to read further, or None when the line is used up.
        """
        line = self._take_contact_columns(line)
        if line is None:
            return None
        if ADDRESS_RE.match(line.strip()):  # "2207 Monroe Street NE, Washington, DC 20018"
            self.contact.read(line)
            return None
        if not self.contact.name and self._take_name(index, line):
            return None
        return line

    def _take_contact_columns(self, line: str) -> str | None:
        """Read "Derek Thompson        (615) 555-0131": its contact columns on their own."""
        columns = split_columns(line)
        items = [column for column in columns
                 if all(is_contact_item(piece) for piece in segments(column))]
        if not items or len(items) >= len(columns):
            return line
        for item in items:
            self.contact.read(item)
        line = "   ".join(column for column in columns if column not in items)
        if self.contact.name or not is_name(name_text(line)):
            # beside contact info: an affiliation or headline, not an entry
            self.found.unplaced.append(UnplacedText(clean(line)))
            return None
        return line

    def _take_name(self, index: int, line: str) -> bool:
        """Take the person's name (or the first half of it) from the line; True if it was."""
        name = name_text(line)
        if is_name(name):
            self.contact.name = name
            return True
        if not (NAME_WORD_RE.match(name.rstrip(".")) and len(name.split()) == 1
                and "," not in line):
            return False
        if self.first_name and index <= _SPLIT_NAME_LINES:
            self.contact.name = f"{self.first_name} {name.rstrip('.')}"
            return True
        if not self.first_name and index == 0:
            self.first_name = name
            return True
        return False

    def _is_credentials(self, line: str) -> bool:
        """Return True for a line of credentials just below the name."""
        return bool(self.contact.name and not self.entries_started
                    and _CREDENTIALS_LINE_RE.fullmatch(line.strip()))

    def _add_entry_or_text(self, line: str) -> None:
        """Start an entry with the line, or keep it as text that fits nowhere."""
        kind = _classify_line(line)
        self.current = None
        if kind is None:
            self._add_text(re.sub(r"\s{2,}", " ", unbullet(line)))
            return
        self.entries_started = True
        self.current = [line]
        if kind is SectionKind.EDUCATION:
            self.found.education_groups.append((self.current, False))
        elif kind is SectionKind.EXPERIENCE:
            self.found.experience_groups.append((self.current, ExperienceKind.WORK))
        else:
            self.found.project_groups.append(self.current)

    def _add_text(self, text: str) -> None:
        """Keep loose text, joining the rest of a summary paragraph onto its start."""
        unplaced = self.found.unplaced
        if unplaced and unplaced[-1].suggestion is None and re.match(r"[a-z]", text):
            # "...I pair qualitative" then "research with ..."
            unplaced[-1].text = f"{unplaced[-1].text} {text}"
        else:
            unplaced.append(UnplacedText(text))
