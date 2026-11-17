"""Resume -> profile (spec 2.12).

`sections_to_profile(sections)` is a pure function over `{header: [lines]}` sections (with
"Other" for lines before the first header), as resume_text.read_resume or resumeRead return them.
It returns `(profile_patch, unplaced, labels)`:

- profile_patch: the API Profile fields it could fill (contact, education, experience, projects,
  skills, links). The name line becomes firstName/middleName/lastName ("Mary Ann Smith" ->
  Mary / Ann / Smith); middleName is "" for a two-word name.
- unplaced: `UnplacedSection`s for text it couldn't place. Header sections keep their header as a
  `"<Header>: "` prefix of `text`, which is how accepting one knows its label.
- labels: the `ResumeParse.sections` lines, `{status, label}`.

Resumes come in many layouts, so entries are found from what their lines look like rather than
from bullet characters (which PDFs often drop): a role starts at a line with dates, the short
lines around it are its title, organization and place, and longer or indented lines are its
bullets. Dates may be "June 2024", "Sep. 2021", "Spring 2024", "03/2021", "2023-03" or a bare
year; a bare year is stored as January of that year.

`parse_into_profile(store, path, ...)` runs in a background thread after POST /resume.
"""
import logging
import re
import threading
import time
from pathlib import Path

from server import resume_text
from server.names import split_name
from server.store import Store

log = logging.getLogger(__name__)

# ----- patterns -----

_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
_YEAR = r"(?:19|20)\d{2}"
_SEASON = r"(?:Spring|Summer|Fall|Autumn|Winter)"
# One date: "June 2024", "Sep. 2021", "Spring 2024", "03/2021", "2023-03" or "2024"
_DATE = (rf"(?:(?<![A-Za-z]){_MONTH}\s*,?\s*{_YEAR}(?!\d)"
         rf"|(?<![A-Za-z]){_SEASON}\s+{_YEAR}(?!\d)"
         rf"|(?<![\d/])(?:0?[1-9]|1[0-2])/{_YEAR}(?![\d/])"
         rf"|(?<![\d-]){_YEAR}-(?:0[1-9]|1[0-2])(?![\d-])"
         rf"|(?<![\w$#.,/]){_YEAR}(?![\w%,]|\.\d))")
_PRESENT = r"(?:present|current|now|today|ongoing)"
MONTH_YEAR_RE = re.compile(rf"(?<![A-Za-z])(?P<month>{_MONTH})\s+(?P<year>\d{{4}})\b", re.I)
RANGE_RE = re.compile(
    rf"(?P<start>{_DATE})(?:\s*(?:to|until|through|–|—|-|\.\.|→)\s*|\s+)"
    rf"(?:(?:Expected|Anticipated|Est\.?)\s+)?(?P<end>{_DATE}|{_PRESENT})(?![A-Za-z])",
    re.I)
# A date on its own; "Present" counts only capitalized, so "now paired with" isn't one
DATE_RE = re.compile(rf"{_DATE}|(?<![A-Za-z])(?-i:Present|PRESENT|Current|Now)(?![A-Za-z])",
                     re.I)
_PRESENT_RE = re.compile(rf"^{_PRESENT}$", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]{0,2}\d{3}[\s.-]{0,2}\d{4}(?!\d)")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s|,;]+"
    r"|(?<![\w@.])(?:[\w-]+\.)+(?:com|io|dev|me|net|org|app|ai|co|us|edu|sh|design|studio|tech"
    r"|page|site|xyz|info)(?:/[^\s|,;\"]*)?(?![\w.])",
    re.I)
GPA_RE = re.compile(r"GPA:?\s*([0-4]\.\d+)", re.I)
SCHOOL_RE = re.compile(r"\b(?:Universit(?:y|é|ät|eit|ad|à|e)|College|Institute|School|Academy"
                       r"|Polytechnic|Conservatory|Seminary|ETH)\b")
_DEGREE_OF = (r"(?:\s+of\s+(?:Applied\s+Science|Science|Arts|Fine\s+Arts|Engineering"
              r"|Business\s+Administration|Accountancy|Public\s+(?:Policy|Health|Administration)"
              r"|Education|Laws|Philosophy|Architecture|Music|Social\s+Work|Nursing|Technology))?")
DEGREE_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    # "Master's", "Master of Science" or "Masters in" — not a bare "Master" ("Master Black Belt")
    rf"(?:Bachelor|Master|Associate|Doctor)(?:['’]s{_DEGREE_OF}|s?{_DEGREE_OF[:-1]}"
    r"|s?(?=\s+(?:in|of|degree)\b))"
    r"|Graduate\s+Certificate|Ph\.?\s?D\.?|[BM]\.?\s?Arch\.?|B\.?Sc\.?|M\.?Sc\.?|M\.?B\.?A\.?"
    r"|M\.?P\.?[PAH]\.?|M\.?S\.?W\.?|M\.?Ed\.?|Ed\.?D\.?|J\.D\.|M\.D\.|B\.?S\.?N\.?|M\.?S\.?N\.?"
    r"|B\.?B\.?A\.?|[BM]\.?Eng\.?|M\.A\.|B\.?S\.?|B\.?A\.?|M\.?S\.?"
    r")(?![A-Za-z])")
BULLET_RE = re.compile(r"^\s*[•●▪◦‣∙·*\-–✓✔➢►▶→◆■□○❖➤]\s*")
COLUMNS_RE = re.compile(r"\s{3,}")
SEGMENT_RE = re.compile(r"\s*[|•·◆◇▪■●⋅✉☎⌂📍📞🔗]\s*|\s{3,}|\s+/\s+")
PROJECT_RE = re.compile(r"^(?P<name>[^()]+?)\s+[-–—]\s+(?P<rest>.+?)\s*\((?P<tech>[^)]+)\)\s*$")
LABEL_RE = re.compile(r"^(?P<label>[^:]{1,40}):\s*(?P<body>.*)$", re.S)
SKILL_PREFIX_RE = re.compile(r"^[A-Za-z][\w /&+-]{0,30}:\s*")
NAME_WORD_RE = re.compile(r"^[A-Z][A-Za-z.'’-]*$")
# "Title: Program Analyst", "Dates: 03/2021 – Present" in a role's head lines
_LABELED_RE = re.compile(r"^(?P<label>[A-Z][A-Za-z /&-]{1,24}):\s*(?P<value>.*)$")
# Splits a head line into its parts: "Title — Org · City, ST", "Title @ Org", "Org  |  Title"
_PART_SPLIT_RE = re.compile(r"\s+[–—|·@•◆]\s+|\s+-\s+|\s{2,}")

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

_MONTH_NUMBERS = {name: i for i, name in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_SEASON_MONTHS = {"spring": 1, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}

# Words that mark a role's title, and words that mark an organization's name
TITLE_WORDS = {
    "engineer", "developer", "designer", "manager", "director", "intern", "internship", "analyst",
    "scientist", "specialist", "coordinator", "assistant", "associate", "consultant",
    "architect", "administrator", "lead", "head", "president", "vice", "officer", "chief", "ceo",
    "cto", "cfo", "coo", "vp", "founder", "co-founder", "teacher", "instructor", "professor",
    "lecturer", "tutor", "researcher", "fellow", "technician", "nurse", "rn", "physician",
    "accountant", "controller", "auditor", "representative", "executive", "supervisor",
    "volunteer", "member", "chair", "treasurer", "secretary", "editor", "writer", "mentor",
    "counselor", "co-op", "coop", "trainee", "apprentice", "clerk", "cashier", "agent",
    "programmer", "strategist", "marketer", "recruiter", "attorney", "paralegal", "ta", "sergeant",
    "advisor", "adviser", "organizer", "principal", "owner", "partner", "senior", "junior", "sr",
    "jr", "captain", "leader", "reliability", "devops", "sre", "sales", "operations",
}
ORG_WORDS = {
    "inc", "llc", "llp", "ltd", "corp", "corporation", "company", "co", "group", "university",
    "college", "institute", "school", "academy", "hospital", "health", "healthcare", "bank",
    "lab", "labs", "laboratory", "department", "agency", "foundation", "association", "society",
    "club", "council", "center", "centre", "studio", "studios", "partners", "technologies",
    "solutions", "services", "consulting", "ventures", "holdings", "capital", "motors",
    "brands", "foods", "products", "logistics", "government", "army", "navy", "federal", "city",
    "county", "administration", "division", "fund", "industries", "supply", "architects",
    "roasters",
}

COURSEWORK_SUGGESTION = "Add to Education"
CUSTOM_SUGGESTION = "Add as a custom field"


# ----- small helpers -----

def _token_iso(token: str) -> str:
    """One date as "YYYY-MM-01" ("" for "Present" or something that isn't a date)."""
    token = token.strip()
    match = MONTH_YEAR_RE.search(token) or re.search(
        rf"(?P<month>{_MONTH})\s*,\s*(?P<year>{_YEAR})", token, re.I)
    if match:
        month = _MONTH_NUMBERS[match.group("month").lower()[:3]]
        return f"{match.group('year')}-{month:02d}-01"
    match = re.search(rf"(?P<season>{_SEASON})\s+(?P<year>{_YEAR})", token, re.I)
    if match:
        return f"{match.group('year')}-{_SEASON_MONTHS[match.group('season').lower()]:02d}-01"
    match = re.search(rf"(?P<month>\d{{1,2}})/(?P<year>{_YEAR})", token)
    if match:
        return f"{match.group('year')}-{int(match.group('month')):02d}-01"
    match = re.search(rf"(?P<year>{_YEAR})-(?P<month>\d{{2}})", token)
    if match:
        return f"{match.group('year')}-{match.group('month')}-01"
    match = re.search(_YEAR, token)
    return f"{match.group(0)}-01-01" if match else ""


def month_iso(text: str) -> str:
    """"June 2026" -> "2026-06-01", "2024" -> "2024-01-01"; "" when there's no date."""
    for match in DATE_RE.finditer(text or ""):
        iso = _token_iso(match.group(0))
        if iso:
            return iso
    return ""


def _clean(text: str) -> str:
    """Trims separators left behind after cutting dates or locations out of a line."""
    text = re.sub(r"\s{2,}", " ", text or "")
    return text.strip(" \t,;|–—-:·•◆/@")


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line)) and not PHONE_RE.match(line.strip())


def _unbullet(line: str) -> str:
    return BULLET_RE.sub("", line, count=1).strip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


# A line that ends on one of these words (or a comma) runs on into the next line
_DANGLING_RE = re.compile(r"(?:[,;&/]|\b(?:and|or|of|for|to|with|by|in|on|at|the|a|an|as|"
                          r"from|into|via|using|including))\s*$", re.I)
_SENTENCE_END_RE = re.compile(r"[.!?;:)]\s*$")
# "Inc." or "P.E." at the end of a line doesn't end a sentence
_ABBREV_END_RE = re.compile(r"(?:\b[A-Z][A-Za-z]{0,3}\.|(?:[A-Z]\.){2,})$")


def _continues(line: str, previous: str, in_bullet: bool) -> bool:
    """True if `line` is the wrapped rest of `previous`, not a line of its own.

    PDFs break long lines where the page ends, so a bullet like "...search by category, and
    bookmark" carries on with "events." on the next line. A line with dates or a column gap is
    a new entry's head, never a continuation.
    """
    text = line.strip()
    if not text or _is_bullet(line) or _has_dates(text) or COLUMNS_RE.search(text):
        return False
    first_word = text.split()[0]
    if first_word[0].islower() and first_word.islower():  # "events.", not "iOS" or "eBay"
        # a short lowercase fragment ("hours", "laude.") never stands on its own
        return (in_bullet or bool(_DANGLING_RE.search(previous))
                or (len(text.split()) <= 3 and bool(re.fullmatch(r"[a-z][a-z\s,.;)'’-]*", text))))
    if _DANGLING_RE.search(previous):  # "Computer Networks," then "Operating Systems"
        return True
    # a line that is only a parenthetical: "(Marketing)" under "B.S., Business Administration"
    if re.fullmatch(r"\([^()]*\)[.,;]?", text) and not _SENTENCE_END_RE.search(previous):
        return True
    # A bullet whose sentence hadn't ended, finished by a line that ends one
    return (in_bullet and not _SENTENCE_END_RE.search(previous)
            and bool(re.search(r"[.!?]\s*$", text)) and "|" not in text)


def join_wrapped(lines: list[str]) -> list[str]:
    """Puts lines that a PDF wrapped back onto the line they continue."""
    joined: list[str] = []
    in_bullet = False
    for line in lines:
        if joined:
            # "Graduate Certificate — University of North Carolina at        2025" then
            # "Charlotte": the text before a right-hand date column is what wraps
            cols = [c for c in COLUMNS_RE.split(joined[-1].strip()) if c]
            if len(cols) > 1 and _has_dates(cols[-1]) and not COLUMNS_RE.search(line.strip()):
                head = "   ".join(cols[:-1])
                if _DANGLING_RE.search(head) and not _has_dates(line):
                    lead = joined[-1][:_indent(joined[-1])]
                    joined[-1] = f"{lead}{head} {line.strip()}     {cols[-1]}"
                    continue
            if _continues(line, joined[-1], in_bullet):
                joined[-1] = f"{joined[-1].rstrip()} {line.strip()}"
                continue
        joined.append(line)
        in_bullet = _is_bullet(line)
    return joined


def _location(text: str) -> tuple[str, str] | None:
    """(city, state) when `text` ends in "City, ST" or "City, State" (a US state)."""
    text = (text or "").strip(" \"'")
    match = LOCATION_RE.search(text)
    if not match:
        return None
    state = match.group("state")
    if state not in US_STATES and state.lower() not in _STATE_NAMES:
        return None
    return match.group("city"), state


def _place(text: str) -> str:
    """"City, ST" when the whole of `text` is a place ("Austin, TX (remote)" too), else ""."""
    bare = re.sub(r"\([^)]*\)", "", text or "").strip(" ,;\"'·")
    if re.fullmatch(r"(?i)remote", bare):
        return "Remote"
    match = LOCATION_RE.fullmatch(bare)
    found = _location(bare)
    return f"{found[0]}, {found[1]}" if match and found else ""


def _strip_location(text: str) -> tuple[str, str]:
    """Cuts a trailing "City, ST" off `text`: (rest, "City, ST")."""
    found = _location(text)
    if not found:
        return text, ""
    match = LOCATION_RE.search(text.strip(" \"'"))
    rest = _clean(text.strip(" \"'")[:match.start()])
    if not rest:  # the whole text is a place: leave it alone
        return text, ""
    return rest, f"{found[0]}, {found[1]}"


def _dates(text: str) -> dict:
    """{start, end, current} from a date range, or from single dates in order."""
    rng = RANGE_RE.search(text or "")
    if rng:
        end_text = rng.group("end")
        current = bool(_PRESENT_RE.match(end_text))
        return {"start": _token_iso(rng.group("start")),
                "end": "" if current else _token_iso(end_text), "current": current}
    tokens = [m.group(0) for m in DATE_RE.finditer(text or "")]
    current = any(_PRESENT_RE.match(t) for t in tokens)
    isos = [iso for iso in (_token_iso(t) for t in tokens) if iso]
    if not isos:
        return {"start": "", "end": "", "current": current}
    if current:
        return {"start": isos[0], "end": "", "current": True}
    return {"start": isos[0] if len(isos) > 1 else "", "end": isos[-1], "current": False}


def _has_dates(text: str) -> bool:
    return bool(RANGE_RE.search(text) or re.search(_DATE, text, re.I))


def _cut_dates(text: str) -> tuple[str, str]:
    """(the dates in `text`, what's left): "Portland · 2021–now" -> ("2021–now", "Portland")."""
    rng = RANGE_RE.search(text)
    found = [rng] if rng else list(DATE_RE.finditer(text))
    if not found:
        return "", text
    dates = " ".join(m.group(0) for m in found)
    rest = text
    for match in reversed(found):
        rest = rest[:match.start()] + " " + rest[match.end():]
    rest = re.sub(r"\b(?:expected|anticipated|dates?|from|since|exp\.)\s*:?\s*$|"
                  r"^\s*(?:expected|anticipated|dates?|from|since|exp\.)\b\s*:?", " ", rest,
                  flags=re.I)
    rest = re.sub(r"\(\s*\)", " ", rest)
    return dates, _clean(rest)


def _date_count(text: str) -> int:
    rng = RANGE_RE.search(text)
    return 2 if rng else len(DATE_RE.findall(text))


def split_line(line: str) -> tuple[str, str, str]:
    """A layout line -> (text, dates text, location).

    Columns are split on 3+ spaces; a right-hand (or left-hand) date column is the dates, a
    column that is only a place is the location. Otherwise a date range inside the text is cut
    out of it.
    """
    cols = [c for c in COLUMNS_RE.split(line.strip()) if c]
    dates = ""
    location = ""
    if len(cols) > 1 and _has_dates(cols[-1]):
        # a date column can carry more: "Computer Science, Colorado School of Mines (2014–2018)"
        dates, rest = _cut_dates(cols.pop())
        if rest:
            cols.append(rest)
    elif len(cols) > 1 and _has_dates(cols[0]) and not _cut_dates(cols[0])[1]:
        dates = cols.pop(0)
    if len(cols) > 1 and _location(cols[-1]) and _location(cols[-1])[0] == cols[-1].split(",")[0]:
        location = cols.pop()
    text = ", ".join(cols)
    if not dates:
        rng = RANGE_RE.search(text)
        if rng:
            dates = rng.group(0)
            text = _clean(text[:rng.start()] + " " + text[rng.end():])
    return _clean(text), dates, location


def split_label(text: str) -> tuple[str | None, str]:
    """"Relevant Coursework: A, B" -> ("Relevant Coursework", "A, B"); (None, text) otherwise."""
    match = LABEL_RE.match(text or "")
    if match and len(match.group("label").split()) <= 4:
        return match.group("label").strip(), match.group("body").strip()
    return None, text


# Header words for sections shaped like jobs (title, organization, dates, bullets) that aren't
# work, and the Experience kind each gives. "Leadership Experience" is a leadership entry.
EXPERIENCE_KIND_WORDS = {"Leadership": "leadership", "Volunteer": "volunteer",
                         "Volunteering": "volunteer", "Community": "volunteer",
                         "Activities": "activity", "Involvement": "activity"}
_EXPERIENCE_WORDS = {"experience", "experiences", "employment", "career", "timeline"}
_SKILLS_WORDS = {"skills", "competencies", "expertise", "proficiencies", "technologies", "tools",
                 "toolkit", "software", "stack"}


def _header_words(header: str) -> list[str]:
    return [word.strip(":,.&").title() for word in header.split()]


def classify_header(header: str) -> str:
    """education|experience|projects|skills|languages|coursework|contact|custom."""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", header)}
    if "contact" in words:
        return "contact"
    if words & {"relevant", "coursework"}:
        return "coursework"
    if "education" in words:
        return "education"
    if words & {"projects", "project"}:
        return "projects"
    if (words & _EXPERIENCE_WORDS or {"work", "history"} <= words
            or any(w.title() in EXPERIENCE_KIND_WORDS for w in words)):
        return "experience"
    if words & _SKILLS_WORDS:
        return "skills"
    if "languages" in words:
        return "languages"
    return "custom"


def experience_kind(header: str) -> str:
    """work|leadership|volunteer|activity for an Experience-type header; "work" by default."""
    for word in _header_words(header):
        if word in EXPERIENCE_KIND_WORDS:
            return EXPERIENCE_KIND_WORDS[word]
    return "work"


def _header_title(header: str) -> str:
    header = header.strip().rstrip(":").strip()
    return header.title() if header.isupper() else header


# ----- contact info -----

def _segments(line: str) -> list[str]:
    return [s.strip() for s in SEGMENT_RE.split(line) if s and s.strip()]


def _contact_item(segment: str) -> bool:
    """True when the whole segment is an email, phone, URL or place (or "Label: one of those")."""
    segment = segment.strip().strip("\"'")
    label = re.match(r"^[A-Za-z][\w ]{0,15}:\s*", segment)
    if label:
        segment = segment[label.end():].strip("\"'")
    return bool(EMAIL_RE.fullmatch(segment) or PHONE_RE.fullmatch(segment)
                or URL_RE.fullmatch(segment)
                or (_location(segment) and LOCATION_RE.fullmatch(segment)))


def _is_contact_line(line: str, early: bool) -> bool:
    segments = _segments(line)
    if segments and all(_contact_item(s) for s in segments):
        return True
    return early and bool(EMAIL_RE.search(line) or PHONE_RE.search(line))


def _is_name(line: str) -> bool:
    words = line.split()
    if not 2 <= len(words) <= 4 or re.search(r"[\d@|,]", line):
        return False
    if SCHOOL_RE.search(line) or DEGREE_RE.search(line):
        return False
    return all(NAME_WORD_RE.match(word) for word in words)


_CREDENTIALS_RE = re.compile(r"(?:,\s*(?:[A-Z]{2,5}|(?:[A-Z]\.){1,3}[A-Z]?\.?))*,?\s*$")


def _name_text(text: str) -> str:
    """"Maria Santos," or "Anthony DiMarco, P.E." -> the bare name; "kenji_watanabe" too."""
    text = text.strip()
    if re.fullmatch(r"[a-z]+[_.][a-z]+", text):
        return text.replace("_", " ").replace(".", " ").title()
    text = _CREDENTIALS_RE.sub("", text).strip()
    return text.title() if text.isupper() else text


def _url(text: str) -> str:
    text = text.rstrip(".")
    # an icon font can leave its glyph's name in front: "inlinkedin.com/in/x", "ghgithub.com/x"
    known = re.search(r"(?:https?://)?(?:www\.)?(?:linkedin|github)\.com\S*", text, re.I)
    if known:
        text = known.group(0)
    return text if re.match(r"https?://", text, re.I) else f"https://{text}"


class _Contact:
    def __init__(self):
        self.name = ""
        self.email = ""
        self.phone = ""
        self.city = ""
        self.state = ""
        self.links: dict[str, str] = {}
        self.extra_links: list[str] = []

    def read(self, line: str) -> None:
        email = EMAIL_RE.search(line)
        if email and not self.email:
            self.email = email.group(0).rstrip(".")
        rest = EMAIL_RE.sub(" ", line)
        phone = PHONE_RE.search(rest)
        if phone and not self.phone:
            self.phone = re.sub(r"\s+", " ", phone.group(0).strip())
        for match in URL_RE.finditer(rest):
            url = _url(match.group(0))
            low = url.lower()
            key = ("linkedin" if "linkedin.com" in low
                   else "github" if "github.com" in low else "web")
            if key not in self.links:
                self.links[key] = url
            elif url not in self.links.values() and url not in self.extra_links:
                self.extra_links.append(url)
        for segment in _segments(rest):
            segment = re.sub(r"^[A-Za-z][\w ]{0,15}:\s*", "", segment)  # "Location: Troy, MI"
            place = _location(segment)
            if place and not self.city:
                self.city, self.state = place

    def count(self) -> int:
        return (sum(bool(v) for v in (self.name, self.email, self.phone)) + bool(self.city)
                + len(self.links) + len(self.extra_links))

    def patch(self) -> dict:
        out = {}
        if self.name:
            out["firstName"], out["middleName"], out["lastName"] = split_name(self.name)
        for key in ("email", "phone", "city", "state"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        if self.links or self.extra_links:
            links = [
                {"id": "web", "label": "Website / portfolio", "url": self.links.get("web", ""),
                 "fixed": True},
                {"id": "linkedin", "label": "LinkedIn", "url": self.links.get("linkedin", ""),
                 "fixed": True},
                {"id": "github", "label": "GitHub", "url": self.links.get("github", ""),
                 "fixed": True},
            ]
            for n, url in enumerate(self.extra_links, 1):
                host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
                links.append({"id": f"link-{n}", "label": host, "url": url, "fixed": False})
            out["links"] = links
        return out


# ----- entries -----

def parse_education(lines: list[str], school: str = "",
                    location: str = "") -> tuple[dict, list[str]]:
    """One degree's lines -> (Education without id, leftover lines).

    `school` and `location` are given for a further degree listed under the previous entry's
    school; the lines then aren't searched for a school.
    """
    entry = {"school": school, "degreeType": "", "major": "", "gpa": "", "location": "",
             "start": "", "end": "", "coursework": ""}
    leftovers: list[str] = []
    date_texts: list[str] = []
    # "M.S., Statistics" then "University of Washington": the school is the line that names one
    school_line = next((i for i, l in enumerate(lines) if SCHOOL_RE.search(l)), 0)
    for index, raw in enumerate(lines):
        line = _unbullet(raw)
        label, body = split_label(line)
        if label and re.search(r"coursework", label, re.I):
            entry["coursework"] = ", ".join(filter(None, [entry["coursework"], body]))
            continue
        # "University of Central Florida · Orlando, FL · May 2020": take the place out first
        segs = re.split(r"\s+[·•|]\s+", line)
        places = [s for s in segs if _place(s) and _place(s) != "Remote"]
        if places:
            if not entry["location"]:
                entry["location"] = _place(places[0])
            line = " · ".join(s for s in segs if s not in places)
        text, dates, place = split_line(line)
        if dates:
            date_texts.append(dates)
        if place and not entry["location"]:
            entry["location"] = place
        used = bool(dates or place or places)
        gpa = GPA_RE.search(text)
        if gpa and not entry["gpa"]:
            entry["gpa"] = gpa.group(1)
            used = True
        degree = DEGREE_RE.search(text)
        if degree and not entry["degreeType"]:
            entry["degreeType"] = degree.group(0).strip()
            after = text[degree.end():]
            after = re.sub(r"^\s*(?:Candidate\b)?[\s,]*(?:(?:in|of)\s+)?", "", after.strip())
            if re.match(r"\s*[-–—]\s", text[degree.end():]):
                after = ""  # "M.Arch — ETH Zürich": the dash brings the school, not a major
            after = re.split(r"\s*[,|(;·]\s*|\s+[-–—]\s+|\s+GPA\b", after, maxsplit=1)[0]
            after = re.split(_DATE, after, maxsplit=1, flags=re.I)[0]
            entry["major"] = "" if SCHOOL_RE.search(after) else _clean(after)
            used = True
        if not entry["school"] and (index == school_line or SCHOOL_RE.search(text)):
            parts = [p for p in re.split(r"\s+[-–—|·]\s+|,\s*", text) if p.strip()]
            school = next((p for p in parts if SCHOOL_RE.search(p)), None)
            if school is None:
                # "ATD Certificate, Instructional Design — Association for Talent Development"
                dashed = re.split(r"\s+[-–—]\s+", text)
                candidates = ([dashed[-1]] if len(dashed) > 1 else []) + parts
                school = next((p for p in candidates if not DEGREE_RE.search(p)
                               and not GPA_RE.search(p) and not _has_dates(p)), "")
            entry["school"] = _clean(re.sub(r"\([^)]*\)", "", school))
            used = used or bool(entry["school"])
        if not dates:
            found, rest = _cut_dates(text)
            if found and not label:
                date_texts.append(found)
                used = used or not rest or rest == entry["school"]
        if not used and text:
            leftovers.append(line)
    if date_texts:
        found = _dates(" ".join(date_texts))
        entry["start"], entry["end"] = found["start"], found["end"]
    if not entry["location"] and entry["school"]:
        entry["school"], entry["location"] = _strip_location(entry["school"])
    entry["location"] = entry["location"] or location
    return entry, leftovers


def _role_words(text: str) -> list[str]:
    return [w.strip(".,()'’").lower() for w in re.findall(r"[A-Za-z][\w.&'’-]*", text)]


def _title_words(text: str) -> int:
    return sum(w in TITLE_WORDS for w in _role_words(text))


def _role_score(text: str) -> int:
    """How title-like `text` is: title words count up, organization words count down."""
    return _title_words(text) - sum(w in ORG_WORDS for w in _role_words(text))


def _org_title(text: str) -> tuple[str, str]:
    """"Org - Title" or "Title, Org" or "Title at Org" -> (org, title).

    Which side is the title is decided by title words ("Engineer", "Intern") against
    organization words ("Inc", "University"); on a tie, "Org - Title" and "Title, Org".
    """
    if re.search(r"\s+at\s+", text):
        title, org = re.split(r"\s+at\s+", text, maxsplit=1)
        return _clean(org), _clean(title)
    parts = re.split(r"\s+[-–—|@·]\s+", text, maxsplit=1)
    if len(parts) == 2:
        first, second = parts
        if _role_score(first) > _role_score(second):
            return _clean(second), _clean(first)
        return _clean(first), _clean(second)
    if "," in text:
        first, second = text.split(",", 1)
        if _role_score(second) > _role_score(first):
            return _clean(first), _clean(second)
        return _clean(second), _clean(first)
    if _role_score(text) > 0:
        return "", _clean(text)
    return _clean(text), ""


_ADDRESS_RE = re.compile(r"^\d+\s+\w.*\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr"
                         r"|Lane|Ln|Way|Suite|NE|NW|SE|SW)\b", re.I)


def parse_experience(lines: list[str], kind: str = "work") -> dict:
    """One role's lines (head lines, then bullets) -> Experience sans id.

    Each head line is split into parts ("Title — Org · City, ST · Jan 2023 – Present"); dates
    and places come out first, "Title:"-style labels are honored, and of what's left the most
    title-like part is the title and the most organization-like one the organization.
    """
    entry = {"kind": kind, "title": "", "org": "", "location": "", "start": "", "end": "",
             "current": False, "detail": ""}
    detail: list[str] = []
    head_detail: list[str] = []
    date_texts: list[str] = []
    parts: list[tuple[int, str]] = []
    labeled = {"title": "", "org": ""}
    for index, raw in enumerate(lines):
        if _is_bullet(raw):
            detail.append(_unbullet(raw))
            continue
        columns = COLUMNS_RE.split(raw.strip())
        for column in columns:
            column_has_dates = _has_dates(column)
            for seg in _PART_SPLIT_RE.split(column):
                seg = seg.strip()
                if not seg:
                    continue
                label = _LABELED_RE.match(seg)
                key = label.group("label").split()[0].lower() if label else ""
                if key in ("title", "position", "role"):
                    labeled["title"] = _clean(re.sub(r"\([^)]*\)", "", label.group("value")))
                    continue
                if key in ("employer", "company", "organization", "agency"):
                    labeled["org"] = _clean(label.group("value"))
                    continue
                if key in ("location", "loc"):
                    entry["location"] = entry["location"] or _clean(label.group("value"))
                    continue
                dates, rest = _cut_dates(seg)
                if dates:
                    date_texts.append(dates)
                if not rest or re.fullmatch(r"\(.*\)", rest):
                    continue
                if label:  # "Hours per week: 40", "Supervisor: ..."
                    head_detail.append(seg)
                    continue
                place = _place(rest)
                if place:
                    entry["location"] = entry["location"] or place
                    continue
                # "Portland · 2021–now": a short name alone beside the dates is the place
                if (column_has_dates and not entry["location"] and len(rest.split()) <= 2
                        and rest[0].isupper() and _role_score(rest) == 0
                        and len([s for s in _PART_SPLIT_RE.split(column) if s.strip()]) == 2
                        and (index > 0 or column is not columns[0])):
                    entry["location"] = rest
                    continue
                rest, trailing = _strip_location(rest)
                if trailing and not entry["location"]:
                    entry["location"] = trailing
                if _ADDRESS_RE.match(rest):
                    continue
                parts.append((index, rest))
    title_part = None
    if labeled["title"]:
        entry["title"] = labeled["title"]
    elif len(parts) == 1:
        entry["org"], entry["title"] = _org_title(parts[0][1])
        title_part = parts[0]
    elif parts:
        scores = [_role_score(text) for _, text in parts]
        best = max(scores)
        # on a tie the later part is the title ("Org - Title", "Org" then "Title")
        title_part = parts[max(i for i, s in enumerate(scores) if s == best)] \
            if scores.count(best) > 1 and best <= 0 else parts[scores.index(best)]
        entry["title"] = title_part[1]
    others = [p for p in parts if p is not title_part]
    if labeled["org"]:
        entry["org"] = labeled["org"]
    elif others and not entry["org"]:
        org_part = min(others, key=lambda p: (_role_score(p[1]), parts.index(p)))
        entry["org"] = org_part[1]
        others.remove(org_part)
    for index, text in others:
        if title_part and index == title_part[0] and entry["title"]:
            entry["title"] = f"{entry['title']} – {text}"
        else:
            head_detail.append(text)
    if date_texts:
        entry.update(_dates(" ".join(date_texts)))
    entry["detail"] = "\n".join(d for d in head_detail + detail if d)
    return entry


def parse_project(lines: list[str]) -> dict:
    """One project's lines -> Project sans id."""
    entry = {"name": "", "tech": "", "detail": ""}
    detail: list[str] = []
    for index, raw in enumerate(lines):
        if _is_bullet(raw):
            detail.append(_unbullet(raw))
            continue
        cols = [c for c in COLUMNS_RE.split(raw.strip()) if c]
        if len(cols) > 1 and _has_dates(cols[-1]):
            cols.pop()
        if len(cols) > 1 and re.fullmatch(r"[0-9a-f]{7,40}", cols[0]):  # a commit hash
            cols.pop(0)
        text = _clean(", ".join(cols))
        if index > 0:
            detail.append(text)
            continue
        match = PROJECT_RE.match(text)
        if match:
            entry["name"] = _clean(match.group("name"))
            entry["tech"] = _clean(match.group("tech"))
            detail.insert(0, _clean(match.group("rest")))
            continue
        if "|" in text:
            name, rest = text.split("|", 1)
            entry["name"], entry["tech"] = _clean(name), _clean(rest)
            continue
        paren = re.match(r"^(?P<name>[^()]+?)\s*\((?P<tech>[^)]+)\)\s*(?P<rest>.*)$", text)
        if paren:
            entry["name"], entry["tech"] = _clean(paren.group("name")), _clean(paren.group("tech"))
            rest = _clean(paren.group("rest"))
            if rest:
                detail.insert(0, rest)
            continue
        parts = re.split(r"\s+[-–—:·]\s+|:\s+", text, maxsplit=1)
        entry["name"] = _clean(parts[0])
        if len(parts) == 2:
            detail.insert(0, _clean(parts[1]))
    entry["detail"] = "\n".join(d for d in detail if d)
    return entry


def _split_items(text: str) -> list[str]:
    """Splits a skills line on , ; | • · and the like, but not inside parentheses."""
    items, depth, current = [], 0, ""
    for char in text:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth <= 0 and char in ",;|•·◆▪✓":
            items.append(current)
            current = ""
            depth = 0
        else:
            current += char
    items.append(current)
    return items


def glue_skill_lines(lines: list[str]) -> list[str]:
    """Rejoins a skills list that wrapped: "Microsoft" then "365 · Miro", "(advanced" then
    "modeling)", "Hemodynamic monitoring" then "(arterial lines, PA catheters)"."""
    glued: list[str] = []
    for raw in lines:
        text = raw.strip()
        labeled = re.match(r"^[\w ]{1,20}:", text)  # "containers:  [Kubernetes, EKS]"
        if glued and text and not labeled and (
                text[0].islower() or text[0].isdigit() or text[0] == "("
                or glued[-1].count("(") > glued[-1].count(")")):
            glued[-1] = f"{glued[-1].rstrip()} {text}"
        else:
            glued.append(raw)
    return glued


def parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for raw in glue_skill_lines(lines):
        line = _unbullet(raw)
        if line.isupper() and ("&" in line or len(line.split()) > 1) and not re.search(
                r"[,·•]", line):
            continue  # a sub-heading like "ML & STATS"
        cols = [c for c in COLUMNS_RE.split(line) if c.strip()]
        # "CAD / PLM      CATIA V5, SolidWorks": the first column is a label
        if (len(cols) > 1 and len(cols[0].split()) <= 3 and "," not in cols[0]
                and re.search(r"[,·•]", " ".join(cols[1:]))):
            cols = cols[1:]
        for col in (c for col in cols for c in re.split(r"\s{2,}", col.strip())):
            col = SKILL_PREFIX_RE.sub("", col.strip()).strip("[] ")
            for item in _split_items(col):
                item = SKILL_PREFIX_RE.sub("", item.strip()).strip("[] ").rstrip(".").strip()
                bare = re.sub(r"\([^)]*\)", "", item)  # "Hemodynamic monitoring (arterial ...)"
                if (item and len(bare) <= 40 and len(bare.split()) <= 5
                        and item.lower() not in seen and re.search(r"[A-Za-z]", item)):
                    seen.add(item.lower())
                    skills.append(item)
    return skills


def _prose(lines: list[str]) -> bool:
    """True when most lines are sentences, not lists (a functional resume's "skills")."""
    cells = [_unbullet(c) for l in lines for c in COLUMNS_RE.split(l.strip()) if c.strip()]
    sentences = [c for c in cells
                 if len(c.split()) >= 5 and len(re.findall(r"[,;·•|]", c)) < 2]
    return len(sentences) >= 0.4 * len(cells)


_SPOKEN_RE = re.compile(r"\b(?:native|fluent|conversational|bilingual|proficien\w*|intermediate"
                        r"|elementary|professional|[ABC][12]|English|Spanish|French|German"
                        r"|Mandarin|Chinese|Hindi|Arabic|Portuguese|Japanese|Korean|Italian"
                        r"|Russian|Tagalog|Bengali|Dutch|Vietnamese|Urdu)\b", re.I)


def _tech_skills(projects: list[dict]) -> list[str]:
    return parse_skills([p["tech"] for p in projects if p.get("tech")])


def _starts_project(line: str) -> bool:
    """"Name | Tech", "Name (Tech)", "Name - what" or "name: what", near the start of a line."""
    cols = COLUMNS_RE.split(line.strip())
    heads = cols[:2] if len(cols) > 1 and len(cols[0].split()) == 1 else cols[:1]
    for text in heads:
        found = re.search(r"\s[-–—|·]\s|\||\(|^[\w.-]+:\s", text)
        if found and found.start() < 40:
            return True
    return False


def _group(lines: list[str], starts_new) -> list[list[str]]:
    """Splits a section's lines into entries; `starts_new(line, group)` decides each boundary."""
    groups: list[list[str]] = []
    for line in lines:
        if not groups or (not _is_bullet(line) and starts_new(line, groups[-1])):
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def _head_like(text: str) -> bool:
    """A short line that could be a title, organization or place, not a sentence."""
    text = text.strip()
    if not text or _is_bullet(text) or text[0].islower() or len(text.split()) > 12:
        return False
    return not (text.endswith((".", ";")) and not _ABBREV_END_RE.search(text))


def _anchor(text: str) -> bool:
    """True for a line whose dates start a role: a range, a date column, or a leading date."""
    text = re.sub(r"\([^)]*\)", " ", text).strip()  # "(converted to permanent 07/2019)"
    label = _LABELED_RE.match(text)
    if label and label.group("label").split()[0].lower() not in ("dates", "date", "period"):
        return False  # "Title: Program Analyst ..." is a head line, never a role's start
    if RANGE_RE.search(text):
        return True
    cols = [c for c in COLUMNS_RE.split(text) if c]
    if len(cols) > 1 and (_has_dates(cols[-1]) or _has_dates(cols[0])):
        return True
    if DATE_RE.match(text):  # "Feb 2023  Senior Marketing Manager"
        return True
    tokens = list(DATE_RE.finditer(text))
    # "Intern Architect — Studio Weiss · 2015": a date that ends a short, capitalized line
    return (bool(tokens) and tokens[-1].end() >= len(text.rstrip(" )")) - 1
            and text[0].isupper() and _head_like(text))


def _has_title_text(text: str) -> bool:
    """False for "Seattle, WA · Apr 2023 – Present": nothing but a place and dates."""
    rest = _cut_dates(text)[1]
    rest = re.sub(r"\([^)]*\)", "", rest)
    pieces = [p for p in _PART_SPLIT_RE.split(rest) if p and _clean(p)]
    return any(not _place(_clean(p)) for p in pieces)


def _continues_role(line: str, previous: str, in_body: bool) -> bool:
    """True if `line` is the wrapped rest of the line before it, inside a role."""
    text = line.strip()
    if not previous or _is_bullet(line):
        return False
    first = text.split()[0]
    if first[0].islower() and first.islower() and not COLUMNS_RE.search(text):
        return True  # but "organizer      Denver DevOps Meetup, 2022–present" is a row
    if re.search(r"[A-Za-z]-$", previous.rstrip()) or _DANGLING_RE.search(previous):
        return True
    if text[0] == "(" and in_body:
        return True
    # "...software; hit" then "124% of quota in 2021": a long sentence that hadn't ended
    if (in_body and (text[0].isdigit() or text[0] in "$%") and not DATE_RE.match(text)
            and not _ADDRESS_RE.match(text) and len(previous.split()) >= 9
            and not _SENTENCE_END_RE.search(previous)):
        return True
    return (in_body and not _SENTENCE_END_RE.search(previous) and len(text.split()) <= 3
            and bool(re.search(r"[.!?]\s*$", text)) and "|" not in text)


def _group_roles(lines: list[str]) -> list[list[str]]:
    """An Experience section -> one list of lines per role: head lines, then "• " bullets.

    A role starts at a line with dates (see `_anchor`). The short lines next to it (before any
    longer or more indented line) are its head; the rest are bullets, with wrapped lines joined.
    When a role's dates sit on its second line, a short line just above them that is less
    indented than the bullets before it (or follows glyph bullets) is pulled into the new role.
    """
    roles: list[dict] = []
    previous = ""
    for line in lines:
        text = line.strip()
        role = roles[-1] if roles else None
        if role and _continues_role(line, previous, bool(role["body"])):
            if role["body"]:
                glue = "" if re.search(r"[A-Za-z]-$", previous.rstrip()) else " "
                role["body"][-1][0] = f"{role['body'][-1][0].rstrip()}{glue}{text}"
                previous = role["body"][-1][0]
            else:
                role["head"][-1] = f"{role['head'][-1].rstrip()} {text}"
                previous = role["head"][-1]
            continue
        previous = text
        if _is_bullet(line):
            if role is None:
                role = {"head": [], "body": [], "dates": 0, "indent": _indent(line)}
                roles.append(role)
            role["body"].append([_unbullet(line), _indent(line), True])
            continue
        if _anchor(text):
            count = _date_count(text)
            if role and not role["body"] and (
                    not role["dates"] or role["dates"] == 1 and count == 1
                    and (_PRESENT_RE.match(DATE_RE.findall(text)[0] or "")
                         or month_iso(text) >= month_iso(" ".join(role["head"])))):
                role["head"].append(line)
                role["dates"] += count
                continue
            new = {"head": [line], "body": [], "dates": count, "indent": _indent(line)}
            if role:
                _pull_head(role, new, _has_title_text(text), _indent(line))
            roles.append(new)
        elif role is None:
            roles.append({"head": [line], "body": [], "dates": 0, "indent": _indent(line)})
        elif (not role["body"] and _head_like(text) and len(role["head"]) < 5
              and _indent(line) <= role["indent"] + 1 and _head_extra(text, role)):
            role["head"].append(line)
        else:
            role["body"].append([text, _indent(line), False])
    return [r["head"] + [f"• {text}" for text, _, _ in r["body"]] for r in roles]


def _head_extra(text: str, role: dict) -> bool:
    """Whether a short line after a role's dated head line is still part of the head.

    Before the dates, any short line is (the title above "City · dates"). After them, only a
    line that is short, has a column gap, names a place, or is "Label: value" — a 7-word
    "Built a dashboard for robot telemetry" is a bullet that lost its bullet character.
    """
    if not role["dates"]:
        return True
    return (len(text.split()) <= 6 or bool(COLUMNS_RE.search(text)) or bool(_LABELED_RE.match(text))
            or any(_place(_clean(p)) for p in _PART_SPLIT_RE.split(text) if _clean(p))
            or bool(_strip_location(text)[1]))


def _pull_head(role: dict, new: dict, has_title: bool, anchor_indent: int) -> None:
    """Moves `role`'s last lines into `new`'s head when they are really its title/org lines.

    Only short lines at the dated line's own indent move, at most three of them.
    """
    body = role["body"]
    if not body:
        return
    first_indent = body[0][1]
    moved: list[str] = []
    while body and len(moved) < 3:
        text, indent, was_bullet = body[-1]
        if (was_bullet or not _head_like(text) or len(text.split()) > 10
                or indent > anchor_indent + 1):
            break
        after_bullets = all(b[2] for b in body[:-1]) and len(body) > 1
        if not (not has_title or indent < first_indent or after_bullets):
            break
        moved.insert(0, " " * indent + text)
        body.pop()
    if moved:
        new["head"][:0] = moved
        new["indent"] = min(_indent(m) for m in moved)


def _new_education(line: str, group: list[str]) -> bool:
    """One line per degree, each with its own date column ("M.S. — Univ. ...      2020")."""
    return _anchor(line) and any(_anchor(g) for g in group) and bool(
        DEGREE_RE.search(line) or SCHOOL_RE.search(line) or COLUMNS_RE.search(line.strip()))


def _group_education(lines: list[str]) -> list[tuple[list[str], bool]]:
    """An Education section -> [(lines, same_school)], one entry per degree.

    A second degree line under one school ("Master of ..." then "Bachelor of ...") starts a new
    entry with `same_school` True: it takes its school from the entry before it.
    """
    groups: list[tuple[list[str], bool]] = []
    for line in lines:
        group = groups[-1][0] if groups else None
        if group is not None and (_is_bullet(line) or line.strip().startswith("(")):
            group.append(line)  # a bullet, or "(MPP)" under "Master of Public Policy"
        elif group is None or (SCHOOL_RE.search(line) and _head_like(line)
                               and any(SCHOOL_RE.search(g) for g in group)):
            groups.append(([line], False))
        elif DEGREE_RE.search(line) and any(DEGREE_RE.search(g) for g in group):
            groups.append(([line], True))
        elif _new_education(line, group):
            groups.append(([line], False))
        else:
            group.append(line)
    return groups


def _new_project(line: str, group: list[str]) -> bool:
    return any(_is_bullet(g) for g in group) or _starts_project(line)


# ----- the mapper -----

def _classify_other(line: str) -> str:
    has_range = bool(RANGE_RE.search(line))
    if DEGREE_RE.search(line):
        return "education"
    if SCHOOL_RE.search(line) and not has_range:
        return "education"
    if has_range:
        return "experience"
    if PROJECT_RE.match(COLUMNS_RE.split(line.strip())[0]):
        return "project"
    return "unplaced"


def _noise(line: str) -> bool:
    """Lines in "Other" that say nothing: "PR" (a monogram), "$14.2M   131%   3×"."""
    text = line.strip()
    letters = len(re.findall(r"[A-Za-z]", text))
    return len(text) <= 3 or letters < 0.35 * len(text.replace(" ", ""))


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _read_other(lines: list[str], contact: _Contact, edu_groups: list, exp_groups: list,
                proj_groups: list, unplaced: list) -> None:
    """The lines before the first header: name, contact info, and any entries."""
    current: list[str] | None = None
    entries_started = False
    first_name = ""  # "Lukas" then "Brenner." on a later line
    for index, line in enumerate(lines):
        if current is not None and _is_bullet(line):
            current.append(line)
            continue
        if not entries_started:
            # "Derek Thompson        (615) 555-0131": read the contact columns on their own
            cols = [c for c in COLUMNS_RE.split(line.strip()) if c]
            items = [c for c in cols if all(_contact_item(s) for s in _segments(c))]
            if items and len(items) < len(cols):
                for item in items:
                    contact.read(item)
                line = "   ".join(c for c in cols if c not in items)
                if contact.name or not _is_name(_name_text(line)):
                    # beside contact info: an affiliation or headline, not an entry
                    unplaced.append((_clean(line), None))
                    continue
            if _ADDRESS_RE.match(line.strip()):  # "2207 Monroe Street NE, Washington, DC 20018"
                contact.read(line)
                continue
            if not contact.name:
                name = _name_text(line)
                if _is_name(name):
                    contact.name = name
                    continue
                if (NAME_WORD_RE.match(name.rstrip(".")) and len(name.split()) == 1
                        and "," not in line):
                    if first_name and index <= 6:
                        contact.name = f"{first_name} {name.rstrip('.')}"
                        continue
                    if not first_name and index == 0:
                        first_name = name
                        continue
        if _is_contact_line(line, early=not entries_started):
            contact.read(line)
            continue
        if _noise(line) or (contact.name and not entries_started and re.fullmatch(
                r"(?:[A-Z]{2,5}|(?:[A-Z]\.)+)(?:,\s*(?:[A-Z]{2,5}|(?:[A-Z]\.)+))+", line.strip())):
            continue  # "BSN, RN, CCRN" beside the name
        kind = _classify_other(line)
        current = None
        if kind == "unplaced":
            text = re.sub(r"\s{2,}", " ", _unbullet(line))
            if unplaced and unplaced[-1][1] is None and re.match(r"[a-z]", text):
                # the rest of a summary paragraph: "...I pair qualitative" / "research with ..."
                unplaced[-1] = (f"{unplaced[-1][0]} {text}", None)
            else:
                unplaced.append((text, None))
            continue
        entries_started = True
        current = [line]
        if kind == "education":
            edu_groups.append((current, False))
        elif kind == "experience":
            exp_groups.append((current, "work"))
        else:
            proj_groups.append(current)
    if first_name and not contact.name:
        contact.name = first_name


def sections_to_profile(sections: dict[str, list[str]]) -> tuple[dict, list[dict], list[dict]]:
    """Resume sections -> (profile_patch, unplaced, labels). Pure; see the module doc."""
    contact = _Contact()
    edu_groups: list[tuple[list[str], bool]] = []
    exp_groups: list[tuple[list[str], str]] = []  # (lines, Experience kind)
    proj_groups: list[list[str]] = []
    skills_lines: list[str] = []
    has_skills_section = False
    unplaced: list[tuple[str, str | None]] = []

    for header, lines in (sections or {}).items():
        lines = join_wrapped([line for line in (lines or []) if line and line.strip()])
        if header == "Other":
            _read_other(lines, contact, edu_groups, exp_groups, proj_groups, unplaced)
            continue

        if not lines:
            continue
        kind = classify_header(header)
        role_kind = experience_kind(header) if kind == "experience" else "work"
        if role_kind != "work" and not any(_anchor(line) for line in lines):
            kind = "custom"  # a list of clubs or awards with no dates isn't a set of roles
        if kind == "languages":
            kind = "custom" if _SPOKEN_RE.search(" ".join(lines)) else "skills"
        if kind == "skills" and _prose(lines):
            kind = "custom"  # a functional resume's "Skills & Accomplishments" paragraphs
        if kind == "coursework":
            # "Relevant Coursework" under Education can be followed by another school
            school_at = next((i for i, l in enumerate(lines) if SCHOOL_RE.search(l)), None)
            if school_at is not None:
                edu_groups.extend(_group_education(lines[school_at:]))
                lines = lines[:school_at]
                if not lines:
                    continue
        if kind == "contact":
            for line in lines:
                contact.read(line)
        elif kind == "education":
            edu_groups.extend(_group_education(lines))
        elif kind == "experience":
            for group in _group_roles(lines):
                head = [g for g in group if not g.startswith("• ")]
                # a degree in a mixed timeline ("2013  B.A., Marketing  /  2017  Marquette"),
                # but not "Master's Researcher" (a title)
                if any(DEGREE_RE.search(h) for h in head) and not _title_words(" ".join(head)):
                    edu_groups.append((head + [g[2:] for g in group if g.startswith("• ")],
                                       False))
                else:
                    exp_groups.append((group, role_kind))
        elif kind == "projects":
            proj_groups.extend(_group(lines, _new_project))
        elif kind == "skills":
            has_skills_section = True
            for line in glue_skill_lines(lines):
                label, body = split_label(_unbullet(line))
                if label and re.search(r"languages", label, re.I) and _SPOKEN_RE.search(body):
                    unplaced.append((f"Languages: {body}", CUSTOM_SUGGESTION))  # spoken ones
                else:
                    skills_lines.append(line)
        else:
            if kind == "coursework":
                body = ", ".join(_clean(item) for line in lines
                                 for item in re.split(r"\s{3,}|\s*[✓•·▪◆]\s*", line)
                                 if _clean(item))
            else:
                body = "; ".join(re.sub(r"\s{2,}", " ", _unbullet(line)) for line in lines)
            suggestion = COURSEWORK_SUGGESTION if kind == "coursework" else CUSTOM_SUGGESTION
            unplaced.append((f"{_header_title(header)}: {body}", suggestion))

    education = []
    for group, same_school in edu_groups:
        if same_school and education and not any(SCHOOL_RE.search(g) for g in group):
            entry, leftovers = parse_education(group, education[-1]["school"],
                                               education[-1]["location"])
        else:
            entry, leftovers = parse_education(group)
        education.append({"id": f"ed-{len(education) + 1}", **entry})
        unplaced.extend((line, COURSEWORK_SUGGESTION) for line in leftovers)
    experience = [{"id": f"x-{n}", **parse_experience(group, role_kind)}
                  for n, (group, role_kind) in enumerate(exp_groups, 1)]
    projects = [{"id": f"p-{n}", **parse_project(g)} for n, g in enumerate(proj_groups, 1)]
    skills = parse_skills(skills_lines) if has_skills_section else _tech_skills(projects)

    patch = contact.patch()
    patch.update(education=education, experience=experience, projects=projects, skills=skills)
    unplaced_out = [{"id": f"un-{n}", "text": text, "suggestion": suggestion}
                    for n, (text, suggestion) in enumerate(unplaced, 1)]

    labels = [{"status": "ok",
               "label": f"Contact info · {_plural(contact.count(), 'field', 'fields')}"}]
    if education:
        labels.append({"status": "ok",
                       "label": f"Education · {education[0]['school'] or len(education)}"})
    if experience:
        labels.append({"status": "ok",
                       "label": f"Experience · {_plural(len(experience), 'role', 'roles')}"})
    if projects:
        labels.append({"status": "ok", "label": f"Projects · {len(projects)}"})
    labels.append({"status": "ok" if has_skills_section and skills else "warn",
                   "label": f"Skills · {len(skills)}"})
    if unplaced_out:
        labels.append({"status": "warn", "label":
                       f"{_plural(len(unplaced_out), 'section', 'sections')} we couldn’t place"})
    return patch, unplaced_out, labels




# ----- the parse job -----

def unreadable(name: str) -> dict:
    return {"code": "unreadable",
            "message": f"We couldn't read text from {name}. Fill your profile in by hand."}


def parse_into_profile(store: Store, path: Path | str, parse_id: str, step_ms: int = 0,
                       name: str | None = None) -> None:
    """Background job for POST /resume: parse, reveal labels one by one, fill the profile.

    Every write first checks that `resume_parse._parseId` is still `parse_id`, so a newer upload
    or DELETE /account makes this job stop quietly. `name` is the uploaded file name.
    """
    path = Path(path)
    name = name or path.name

    def still_current(db) -> bool:
        parse = db.resume_parse
        return isinstance(parse, dict) and parse.get("_parseId") == parse_id

    try:
        sections = resume_text.read_resume(path)
        result = sections_to_profile(sections) if sections else None
    except Exception as error:  # pylint: disable=broad-except
        log.warning("Resume parse failed for %s: %s", name, type(error).__name__)
        log.debug("Resume parse error", exc_info=True)
        sections, result = None, None

    if result is None:
        with store.tx() as db:
            if still_current(db):
                db.resume_parse.update(status="failed", error=unreadable(name))
        return

    patch, unplaced, labels = result
    for label in labels:
        if step_ms > 0:
            time.sleep(step_ms / 1000)
        with store.tx() as db:
            if not still_current(db):
                return
            db.resume_parse["sections"].append(label)

    with store.tx() as db:
        if not still_current(db):
            return
        db.profile.update(patch)
        db.profile["unplaced"] = unplaced
        db.resume_parse.update(status="done", _rawSections=sections)


def start_parse(store: Store, path: Path | str, parse_id: str, step_ms: int,
                name: str | None = None) -> threading.Thread:
    """Runs parse_into_profile in a daemon thread."""
    thread = threading.Thread(target=parse_into_profile,
                              args=(store, path, parse_id, step_ms, name),
                              name="resume-parse", daemon=True)
    thread.start()
    return thread
