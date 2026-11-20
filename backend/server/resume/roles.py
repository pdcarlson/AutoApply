"""Splits an Experience section's lines into one group of lines per role."""
import re
from dataclasses import dataclass, field

from server.resume.dates import DATE_RE, PRESENT_RE, date_count, month_iso
from server.resume.line_shapes import has_title_text, is_anchor, is_head_like
from server.resume.line_text import clean, indent, is_bullet, unbullet
from server.resume.patterns import (ADDRESS_RE, COLUMNS_RE, DANGLING_RE, LABELED_RE,
                                    PART_SPLIT_RE, SENTENCE_END_RE)
from server.resume.places import as_place, strip_location

_HYPHEN_END_RE = re.compile(r"[A-Za-z]-$")


@dataclass
class _BodyLine:
    """One line of a role's body, remembering how it looked on the page."""

    text: str
    indent: int
    was_bullet: bool


@dataclass
class _Role:
    """The lines of one role found so far: head lines, then body lines."""

    head: list[str]
    indent: int
    dates: int = 0
    body: list[_BodyLine] = field(default_factory=list)

    def lines(self) -> list[str]:
        """Return the head lines, then each body line as a "• " bullet."""
        return self.head + [f"• {line.text}" for line in self.body]

    def append_wrapped(self, text: str, previous: str) -> str:
        """Join a wrapped line onto the role's last line and return that line."""
        if self.body:
            glue = "" if _HYPHEN_END_RE.search(previous.rstrip()) else " "
            self.body[-1].text = f"{self.body[-1].text.rstrip()}{glue}{text}"
            return self.body[-1].text
        self.head[-1] = f"{self.head[-1].rstrip()} {text}"
        return self.head[-1]


def group_roles(lines: list[str]) -> list[list[str]]:
    """Split an Experience section into one list of lines per role: head lines, then bullets.

    A role starts at a line with dates (see `is_anchor`). The short lines next to it (before any
    longer or more indented line) are its head; the rest are bullets, with wrapped lines joined.
    When a role's dates sit on its second line, a short line just above them that is less
    indented than the bullets before it (or follows glyph bullets) is pulled into the new role.
    """
    roles: list[_Role] = []
    previous = ""
    for line in lines:
        role = roles[-1] if roles else None
        if role and _continues_role(line, previous, bool(role.body)):
            previous = role.append_wrapped(line.strip(), previous)
            continue
        previous = line.strip()
        new_role = _add_line(role, line)
        if new_role is not None:
            roles.append(new_role)
    return [role.lines() for role in roles]


def _add_line(role: _Role | None, line: str) -> _Role | None:
    """Add the line to the current role, or return the new role it starts."""
    text = line.strip()
    if is_bullet(line):
        new_role = _Role([], indent(line)) if role is None else None
        (new_role or role).body.append(_BodyLine(unbullet(line), indent(line), True))
        return new_role
    if is_anchor(text):
        count = date_count(text)
        if role and _joins_dated_head(role, text, count):
            role.head.append(line)
            role.dates += count
            return None
        new_role = _Role([line], indent(line), count)
        if role:
            _pull_head(role, new_role, has_title_text(text), indent(line))
        return new_role
    if role is None:
        return _Role([line], indent(line))
    if (not role.body and is_head_like(text) and len(role.head) < 5
            and indent(line) <= role.indent + 1 and _is_head_extra(text, role)):
        role.head.append(line)
    else:
        role.body.append(_BodyLine(text, indent(line), False))
    return None


def _joins_dated_head(role: _Role, text: str, count: int) -> bool:
    """Return True when a dated line still belongs to the head of the role before it."""
    if role.body:
        return False
    if not role.dates:
        return True
    if role.dates != 1 or count != 1:
        return False
    return (bool(PRESENT_RE.match(DATE_RE.findall(text)[0] or ""))
            or month_iso(text) >= month_iso(" ".join(role.head)))


def _continues_role(line: str, previous: str, in_body: bool) -> bool:
    """Return True if `line` is the wrapped rest of the line before it, inside a role."""
    text = line.strip()
    if not previous or is_bullet(line):
        return False
    first = text.split()[0]
    if first[0].islower() and first.islower() and not COLUMNS_RE.search(text):
        return True  # but "organizer      Denver DevOps Meetup, 2022–present" is a row
    if _HYPHEN_END_RE.search(previous.rstrip()) or DANGLING_RE.search(previous):
        return True
    if text[0] == "(" and in_body:
        return True
    if in_body and _finishes_long_sentence(text, previous):
        return True
    return (in_body and not SENTENCE_END_RE.search(previous) and len(text.split()) <= 3
            and bool(re.search(r"[.!?]\s*$", text)) and "|" not in text)


def _finishes_long_sentence(text: str, previous: str) -> bool:
    """Return True for "...software; hit" then "124% of quota in 2021": a sentence carried on."""
    starts_with_number = text[0].isdigit() or text[0] in "$%"
    if not starts_with_number or DATE_RE.match(text) or ADDRESS_RE.match(text):
        return False
    return len(previous.split()) >= 9 and not SENTENCE_END_RE.search(previous)


def _is_head_extra(text: str, role: _Role) -> bool:
    """Return whether a short line after a role's dated head line is still part of the head.

    Before the dates, any short line is (the title above "City · dates"). After them, only a
    line that is short, has a column gap, names a place, or is "Label: value" — a 7-word
    "Built a dashboard for robot telemetry" is a bullet that lost its bullet character.
    """
    if not role.dates:
        return True
    return (len(text.split()) <= 6 or bool(COLUMNS_RE.search(text)) or bool(LABELED_RE.match(text))
            or any(as_place(clean(piece)) for piece in PART_SPLIT_RE.split(text) if clean(piece))
            or bool(strip_location(text)[1]))


def _pull_head(role: _Role, new_role: _Role, has_title: bool, anchor_indent: int) -> None:
    """Move `role`'s last lines into `new_role`'s head when they are really its title lines.

    Only short lines at the dated line's own indent move, at most three of them.
    """
    body = role.body
    if not body:
        return
    first_indent = body[0].indent
    moved: list[str] = []
    while body and len(moved) < 3:
        last = body[-1]
        if (last.was_bullet or not is_head_like(last.text) or len(last.text.split()) > 10
                or last.indent > anchor_indent + 1):
            break
        after_bullets = all(line.was_bullet for line in body[:-1]) and len(body) > 1
        if has_title and last.indent >= first_indent and not after_bullets:
            break
        moved.insert(0, " " * last.indent + last.text)
        body.pop()
    if moved:
        new_role.head[:0] = moved
        new_role.indent = min(indent(line) for line in moved)
