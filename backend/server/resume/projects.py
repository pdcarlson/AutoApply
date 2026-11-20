"""Reads the Projects section of a resume into ProjectEntry objects."""
import re

from server.resume.dates import has_dates
from server.resume.entries import ProjectEntry
from server.resume.layout import split_columns
from server.resume.line_text import clean, is_bullet, unbullet
from server.resume.patterns import COLUMNS_RE, PROJECT_RE

_COMMIT_HASH_RE = re.compile(r"[0-9a-f]{7,40}")
_NAME_TECH_RE = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<tech>[^)]+)\)\s*(?P<rest>.*)$")


def group_projects(lines: list[str]) -> list[list[str]]:
    """Split a Projects section into one list of lines per project."""
    groups: list[list[str]] = []
    for line in lines:
        if not groups or (not is_bullet(line) and _starts_new_project(line, groups[-1])):
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def _starts_new_project(line: str, group: list[str]) -> bool:
    """Return True when the line starts a project after the current one."""
    return any(is_bullet(earlier) for earlier in group) or _looks_like_project_head(line)


def _looks_like_project_head(line: str) -> bool:
    """Return True for "Name | Tech", "Name (Tech)", "Name - what" or "name: what"."""
    columns = COLUMNS_RE.split(line.strip())
    heads = columns[:2] if len(columns) > 1 and len(columns[0].split()) == 1 else columns[:1]
    for text in heads:
        found = re.search(r"\s[-–—|·]\s|\||\(|^[\w.-]+:\s", text)
        if found and found.start() < 40:
            return True
    return False


def parse_project(lines: list[str]) -> ProjectEntry:
    """Read one project's lines into a ProjectEntry."""
    entry = ProjectEntry()
    detail: list[str] = []
    for index, raw in enumerate(lines):
        if is_bullet(raw):
            detail.append(unbullet(raw))
            continue
        text = _head_text(raw)
        if index > 0:
            detail.append(text)
            continue
        description = _read_head(entry, text)
        if description:
            detail.insert(0, description)
    entry.detail = "\n".join(text for text in detail if text)
    return entry


def _head_text(line: str) -> str:
    """Return a project line without a right-hand date column or a leading commit hash."""
    columns = split_columns(line)
    if len(columns) > 1 and has_dates(columns[-1]):
        columns.pop()
    if len(columns) > 1 and _COMMIT_HASH_RE.fullmatch(columns[0]):
        columns.pop(0)
    return clean(", ".join(columns))


def _read_head(entry: ProjectEntry, text: str) -> str:
    """Fill the project's name and tech from its first line; return any description on it."""
    match = PROJECT_RE.match(text)
    if match:
        entry.name, entry.tech = clean(match.group("name")), clean(match.group("tech"))
        return clean(match.group("rest"))
    if "|" in text:
        name, rest = text.split("|", 1)
        entry.name, entry.tech = clean(name), clean(rest)
        return ""
    with_tech = _NAME_TECH_RE.match(text)
    if with_tech:
        entry.name, entry.tech = clean(with_tech.group("name")), clean(with_tech.group("tech"))
        return clean(with_tech.group("rest"))
    parts = re.split(r"\s+[-–—:·]\s+|:\s+", text, maxsplit=1)
    entry.name = clean(parts[0])
    return clean(parts[1]) if len(parts) == 2 else ""
