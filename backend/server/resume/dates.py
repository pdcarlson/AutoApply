"""Finds dates and date ranges in resume lines and turns them into ISO months."""
import re
from dataclasses import dataclass

from server.resume.line_text import clean

MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
         r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
YEAR = r"(?:19|20)\d{2}"
SEASON = r"(?:Spring|Summer|Fall|Autumn|Winter)"
# One date: "June 2024", "Sep. 2021", "Spring 2024", "03/2021", "2023-03" or "2024"
DATE = (rf"(?:(?<![A-Za-z]){MONTH}\s*,?\s*{YEAR}(?!\d)"
        rf"|(?<![A-Za-z]){SEASON}\s+{YEAR}(?!\d)"
        rf"|(?<![\d/])(?:0?[1-9]|1[0-2])/{YEAR}(?![\d/])"
        rf"|(?<![\d-]){YEAR}-(?:0[1-9]|1[0-2])(?![\d-])"
        rf"|(?<![\w$#.,/]){YEAR}(?![\w%,]|\.\d))")
PRESENT = r"(?:present|current|now|today|ongoing)"
MONTH_YEAR_RE = re.compile(rf"(?<![A-Za-z])(?P<month>{MONTH})\s+(?P<year>\d{{4}})\b", re.I)
RANGE_RE = re.compile(
    rf"(?P<start>{DATE})(?:\s*(?:to|until|through|–|—|-|\.\.|→)\s*|\s+)"
    rf"(?:(?:Expected|Anticipated|Est\.?)\s+)?(?P<end>{DATE}|{PRESENT})(?![A-Za-z])",
    re.I)
# A date on its own; "Present" counts only capitalized, so "now paired with" isn't one
DATE_RE = re.compile(rf"{DATE}|(?<![A-Za-z])(?-i:Present|PRESENT|Current|Now)(?![A-Za-z])",
                     re.I)
PRESENT_RE = re.compile(rf"^{PRESENT}$", re.I)

_MONTH_NUMBERS = {name: i for i, name in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
# A season has no month, so it is stored as the month that season starts
_SEASON_MONTHS = {"spring": 1, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}


@dataclass
class DateRange:
    """When an entry started and ended, as "YYYY-MM-01" strings ("" when unknown)."""

    start: str = ""
    end: str = ""
    current: bool = False


def token_iso(token: str) -> str:
    """Return one date as "YYYY-MM-01", or "" for "Present" or something that isn't a date."""
    token = token.strip()
    match = MONTH_YEAR_RE.search(token) or re.search(
        rf"(?P<month>{MONTH})\s*,\s*(?P<year>{YEAR})", token, re.I)
    if match:
        month = _MONTH_NUMBERS[match.group("month").lower()[:3]]
        return f"{match.group('year')}-{month:02d}-01"
    match = re.search(rf"(?P<season>{SEASON})\s+(?P<year>{YEAR})", token, re.I)
    if match:
        return f"{match.group('year')}-{_SEASON_MONTHS[match.group('season').lower()]:02d}-01"
    match = re.search(rf"(?P<month>\d{{1,2}})/(?P<year>{YEAR})", token)
    if match:
        return f"{match.group('year')}-{int(match.group('month')):02d}-01"
    match = re.search(rf"(?P<year>{YEAR})-(?P<month>\d{{2}})", token)
    if match:
        return f"{match.group('year')}-{match.group('month')}-01"
    match = re.search(YEAR, token)
    return f"{match.group(0)}-01-01" if match else ""


def month_iso(text: str) -> str:
    """Return the first date in `text` ("June 2026" -> "2026-06-01"), or "" when there is none."""
    for match in DATE_RE.finditer(text or ""):
        iso = token_iso(match.group(0))
        if iso:
            return iso
    return ""


def read_dates(text: str) -> DateRange:
    """Return the DateRange of a date range, or of single dates taken in order."""
    found_range = RANGE_RE.search(text or "")
    if found_range:
        end_text = found_range.group("end")
        current = bool(PRESENT_RE.match(end_text))
        return DateRange(token_iso(found_range.group("start")),
                         "" if current else token_iso(end_text), current)
    tokens = [match.group(0) for match in DATE_RE.finditer(text or "")]
    current = any(PRESENT_RE.match(token) for token in tokens)
    isos = [iso for iso in (token_iso(token) for token in tokens) if iso]
    if not isos:
        return DateRange("", "", current)
    if current:
        return DateRange(isos[0], "", True)
    return DateRange(isos[0] if len(isos) > 1 else "", isos[-1], False)


def has_dates(text: str) -> bool:
    """Return True when `text` holds a date or a date range."""
    return bool(RANGE_RE.search(text) or re.search(DATE, text, re.I))


def cut_dates(text: str) -> tuple[str, str]:
    """Split `text` into (dates, rest): "Portland · 2021–now" -> ("2021–now", "Portland")."""
    found_range = RANGE_RE.search(text)
    found = [found_range] if found_range else list(DATE_RE.finditer(text))
    if not found:
        return "", text
    dates = " ".join(match.group(0) for match in found)
    rest = text
    for match in reversed(found):
        rest = rest[:match.start()] + " " + rest[match.end():]
    rest = re.sub(r"\b(?:expected|anticipated|dates?|from|since|exp\.)\s*:?\s*$|"
                  r"^\s*(?:expected|anticipated|dates?|from|since|exp\.)\b\s*:?", " ", rest,
                  flags=re.I)
    rest = re.sub(r"\(\s*\)", " ", rest)
    return dates, clean(rest)


def date_count(text: str) -> int:
    """Return how many dates `text` holds, counting a range as two."""
    found_range = RANGE_RE.search(text)
    return 2 if found_range else len(DATE_RE.findall(text))
