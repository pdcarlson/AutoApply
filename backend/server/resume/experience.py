"""Reads one role's lines from a resume into an ExperienceEntry."""
import re

from server.resume.dates import cut_dates, has_dates, read_dates
from server.resume.entries import ExperienceEntry
from server.resume.line_text import clean, is_bullet, unbullet
from server.resume.patterns import ADDRESS_RE, COLUMNS_RE, LABELED_RE, PART_SPLIT_RE
from server.resume.places import as_place, strip_location
from server.resume.section_kind import ExperienceKind
from server.resume.titles import role_score, split_org_title

_TITLE_LABELS = ("title", "position", "role")
_ORG_LABELS = ("employer", "company", "organization", "agency")
_LOCATION_LABELS = ("location", "loc")


def parse_experience(lines: list[str],
                     kind: ExperienceKind = ExperienceKind.WORK) -> ExperienceEntry:
    """Read one role's lines (head lines, then bullets) into an ExperienceEntry.

    Each head line is split into parts ("Title — Org · City, ST · Jan 2023 – Present"); dates
    and places come out first, "Title:"-style labels are honored, and of what's left the most
    title-like part is the title and the most organization-like one the organization.
    """
    return _ExperienceReader(kind).read(lines)


class _ExperienceReader:  # pylint: disable=too-few-public-methods  # one reader per call, used through read()
    """Reads one role's lines, filling one ExperienceEntry."""

    def __init__(self, kind: ExperienceKind):
        self.entry = ExperienceEntry(kind=kind)
        self.detail: list[str] = []
        self.head_detail: list[str] = []
        self.date_texts: list[str] = []
        self.parts: list[tuple[int, str]] = []  # (line index, text) of each unplaced head part
        self.labeled_title = ""
        self.labeled_org = ""

    def read(self, lines: list[str]) -> ExperienceEntry:
        """Return the entry the lines describe."""
        for index, raw in enumerate(lines):
            if is_bullet(raw):
                self.detail.append(unbullet(raw))
                continue
            columns = COLUMNS_RE.split(raw.strip())
            for column in columns:
                after_start = index > 0 or column is not columns[0]
                for part in PART_SPLIT_RE.split(column):
                    if part.strip():
                        self._read_part(part.strip(), index, column, after_start)
        self._choose_title_and_org()
        if self.date_texts:
            found = read_dates(" ".join(self.date_texts))
            self.entry.start, self.entry.end, self.entry.current = (
                found.start, found.end, found.current)
        self.entry.detail = "\n".join(text for text in self.head_detail + self.detail if text)
        return self.entry

    def _read_part(self, part: str, index: int, column: str, after_start: bool) -> None:
        """Take dates, a place or a labeled value from one head part, or keep it for later."""
        if self._take_labeled(part):
            return
        dates, rest = cut_dates(part)
        if dates:
            self.date_texts.append(dates)
        if not rest or re.fullmatch(r"\(.*\)", rest):
            return
        if LABELED_RE.match(part):  # "Hours per week: 40", "Supervisor: ..."
            self.head_detail.append(part)
            return
        place = as_place(rest)
        if place:
            self.entry.location = self.entry.location or place
            return
        if not self.entry.location and after_start and _is_place_beside_dates(rest, column):
            self.entry.location = rest
            return
        rest, trailing = strip_location(rest)
        if trailing and not self.entry.location:
            self.entry.location = trailing
        if not ADDRESS_RE.match(rest):
            self.parts.append((index, rest))

    def _take_labeled(self, part: str) -> bool:
        """Take a "Title: ...", "Employer: ..." or "Location: ..." part; True if it was one."""
        label = LABELED_RE.match(part)
        key = label.group("label").split()[0].lower() if label else ""
        if key in _TITLE_LABELS:
            self.labeled_title = clean(re.sub(r"\([^)]*\)", "", label.group("value")))
        elif key in _ORG_LABELS:
            self.labeled_org = clean(label.group("value"))
        elif key in _LOCATION_LABELS:
            self.entry.location = self.entry.location or clean(label.group("value"))
        else:
            return False
        return True

    def _choose_title_and_org(self) -> None:
        """Pick the title and organization from the head parts; the rest become detail."""
        title_part = self._pick_title_part()
        others = [part for part in self.parts if part is not title_part]
        if self.labeled_org:
            self.entry.org = self.labeled_org
        elif others and not self.entry.org:
            org_part = min(others, key=lambda part: (role_score(part[1]), self.parts.index(part)))
            self.entry.org = org_part[1]
            others.remove(org_part)
        for index, text in others:
            if title_part and index == title_part[0] and self.entry.title:
                self.entry.title = f"{self.entry.title} – {text}"
            else:
                self.head_detail.append(text)

    def _pick_title_part(self) -> tuple[int, str] | None:
        """Set the title and return the head part it came from (None for a labeled title)."""
        parts = self.parts
        if self.labeled_title:
            self.entry.title = self.labeled_title
            return None
        if len(parts) == 1:
            self.entry.org, self.entry.title = split_org_title(parts[0][1])
            return parts[0]
        if not parts:
            return None
        scores = [role_score(text) for _, text in parts]
        best = max(scores)
        if scores.count(best) > 1 and best <= 0:
            # on a tie the later part is the title ("Org - Title", "Org" then "Title")
            title_part = parts[max(i for i, score in enumerate(scores) if score == best)]
        else:
            title_part = parts[scores.index(best)]
        self.entry.title = title_part[1]
        return title_part


def _is_place_beside_dates(rest: str, column: str) -> bool:
    """Return True for "Portland · 2021–now": a short name alone beside the dates is the place."""
    return (has_dates(column) and len(rest.split()) <= 2 and rest[0].isupper()
            and role_score(rest) == 0
            and len([piece for piece in PART_SPLIT_RE.split(column) if piece.strip()]) == 2)
