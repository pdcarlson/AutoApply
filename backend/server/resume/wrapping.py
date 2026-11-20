"""Puts resume lines that a PDF wrapped back onto the line they continue."""
import re

from server.resume.dates import has_dates
from server.resume.layout import split_columns
from server.resume.line_text import indent, is_bullet
from server.resume.patterns import COLUMNS_RE, DANGLING_RE, SENTENCE_END_RE


def join_wrapped(lines: list[str]) -> list[str]:
    """Return the lines with each wrapped piece joined back onto the line it continues."""
    joined: list[str] = []
    in_bullet = False
    for line in lines:
        if joined:
            rejoined = _rejoin_before_date_column(joined[-1], line)
            if rejoined is not None:
                joined[-1] = rejoined
                continue
            if _continues(line, joined[-1], in_bullet):
                joined[-1] = f"{joined[-1].rstrip()} {line.strip()}"
                continue
        joined.append(line)
        in_bullet = is_bullet(line)
    return joined


def _rejoin_before_date_column(previous: str, line: str) -> str | None:
    """Return `previous` with `line` joined before its date column, or None if it doesn't wrap.

    "Graduate Certificate — University of North Carolina at        2025" then "Charlotte": the
    text before a right-hand date column is what wraps.
    """
    columns = split_columns(previous)
    if len(columns) > 1 and has_dates(columns[-1]) and not COLUMNS_RE.search(line.strip()):
        head = "   ".join(columns[:-1])
        if DANGLING_RE.search(head) and not has_dates(line):
            lead = previous[:indent(previous)]
            return f"{lead}{head} {line.strip()}     {columns[-1]}"
    return None


def _continues(line: str, previous: str, in_bullet: bool) -> bool:
    """Return True if `line` is the wrapped rest of `previous`, not a line of its own.

    PDFs break long lines where the page ends, so a bullet like "...search by category, and
    bookmark" carries on with "events." on the next line. A line with dates or a column gap is
    a new entry's head, never a continuation.
    """
    text = line.strip()
    if not text or is_bullet(line) or has_dates(text) or COLUMNS_RE.search(text):
        return False
    first_word = text.split()[0]
    if first_word[0].islower() and first_word.islower():  # "events.", not "iOS" or "eBay"
        # a short lowercase fragment ("hours", "laude.") never stands on its own
        return (in_bullet or bool(DANGLING_RE.search(previous))
                or (len(text.split()) <= 3 and bool(re.fullmatch(r"[a-z][a-z\s,.;)'’-]*", text))))
    if DANGLING_RE.search(previous):  # "Computer Networks," then "Operating Systems"
        return True
    # a line that is only a parenthetical: "(Marketing)" under "B.S., Business Administration"
    if re.fullmatch(r"\([^()]*\)[.,;]?", text) and not SENTENCE_END_RE.search(previous):
        return True
    # A bullet whose sentence hadn't ended, finished by a line that ends one
    return (in_bullet and not SENTENCE_END_RE.search(previous)
            and bool(re.search(r"[.!?]\s*$", text)) and "|" not in text)
