"""Finds US places ("City, ST" or "City, State") in resume text."""
import re

from server.resume.line_text import clean

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin",
    "WY": "Wyoming", "PR": "Puerto Rico",
}
_STATE_NAMES = {name.lower() for name in US_STATES.values()}
LOCATION_RE = re.compile(
    r"(?P<city>(?:[A-Z][A-Za-z.'’-]+\s){0,2}[A-Z][A-Za-z.'’-]+),\s*"
    r"(?P<state>[A-Z]{2}|[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})(?:\s+\d{5}(?:-\d{4})?)?\s*$")


def find_location(text: str) -> tuple[str, str] | None:
    """Return (city, state) when `text` ends in "City, ST" or "City, State", else None."""
    text = (text or "").strip(" \"'")
    match = LOCATION_RE.search(text)
    if not match:
        return None
    state = match.group("state")
    if state not in US_STATES and state.lower() not in _STATE_NAMES:
        return None
    return match.group("city"), state


def as_place(text: str) -> str:
    """Return "City, ST" when all of `text` is a place ("Austin, TX (remote)" too), else ""."""
    bare = re.sub(r"\([^)]*\)", "", text or "").strip(" ,;\"'·")
    if re.fullmatch(r"(?i)remote", bare):
        return "Remote"
    match = LOCATION_RE.fullmatch(bare)
    found = find_location(bare)
    return f"{found[0]}, {found[1]}" if match and found else ""


def strip_location(text: str) -> tuple[str, str]:
    """Cut a trailing "City, ST" off `text`, returning (rest, "City, ST")."""
    found = find_location(text)
    if not found:
        return text, ""
    match = LOCATION_RE.search(text.strip(" \"'"))
    rest = clean(text.strip(" \"'")[:match.start()])
    if not rest:  # the whole text is a place: leave it alone
        return text, ""
    return rest, f"{found[0]}, {found[1]}"
