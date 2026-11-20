"""Tells what an entry's line looks like: a dated start, or a short head line."""
import re

from server.resume.dates import DATE_RE, RANGE_RE, cut_dates, has_dates
from server.resume.layout import split_columns
from server.resume.line_text import clean, is_bullet
from server.resume.patterns import ABBREV_END_RE, LABELED_RE, PART_SPLIT_RE
from server.resume.places import as_place


def is_head_like(text: str) -> bool:
    """Return True for a short line that could be a title, organization or place."""
    text = text.strip()
    if not text or is_bullet(text) or text[0].islower() or len(text.split()) > 12:
        return False
    return not (text.endswith((".", ";")) and not ABBREV_END_RE.search(text))


def is_anchor(text: str) -> bool:
    """Return True for a line whose dates start a role: a range, a date column, a leading date."""
    text = re.sub(r"\([^)]*\)", " ", text).strip()  # "(converted to permanent 07/2019)"
    label = LABELED_RE.match(text)
    if label and label.group("label").split()[0].lower() not in ("dates", "date", "period"):
        return False  # "Title: Program Analyst ..." is a head line, never a role's start
    if RANGE_RE.search(text):
        return True
    columns = split_columns(text)
    if len(columns) > 1 and (has_dates(columns[-1]) or has_dates(columns[0])):
        return True
    if DATE_RE.match(text):  # "Feb 2023  Senior Marketing Manager"
        return True
    tokens = list(DATE_RE.finditer(text))
    # "Intern Architect — Studio Weiss · 2015": a date that ends a short, capitalized line
    return (bool(tokens) and tokens[-1].end() >= len(text.rstrip(" )")) - 1
            and text[0].isupper() and is_head_like(text))


def has_title_text(text: str) -> bool:
    """Return False for "Seattle, WA · Apr 2023 – Present": nothing but a place and dates."""
    rest = cut_dates(text)[1]
    rest = re.sub(r"\([^)]*\)", "", rest)
    pieces = [piece for piece in PART_SPLIT_RE.split(rest) if piece and clean(piece)]
    return any(not as_place(clean(piece)) for piece in pieces)
