"""Resume -> profile (spec 2.12).

`sections_to_profile(sections)` is a pure function over resumeRead's `{header: [lines]}` output
(with "Other" for lines before the first header). It returns `(profile_patch, unplaced, labels)`:

- profile_patch: the API Profile fields it could fill (contact, education, experience, projects,
  skills, links). The name line becomes firstName/middleName/lastName ("Mary Ann Smith" ->
  Mary / Ann / Smith); middleName is "" for a two-word name.
- unplaced: `UnplacedSection`s for text it couldn't place. Header sections keep their header as a
  `"<Header>: "` prefix of `text`, which is how accepting one knows its label.
- labels: the `ResumeParse.sections` lines, `{status, label}`.

`parse_into_profile(store, path, ...)` runs in a background thread after POST /resume.
"""
import logging
import re
import threading
import time
from pathlib import Path

from server import konefal
from server.names import split_name
from server.store import Store

log = logging.getLogger(__name__)

# ----- patterns -----

_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
_MONTH_YEAR = rf"{_MONTH}\s+\d{{4}}"
MONTH_YEAR_RE = re.compile(rf"(?<![A-Za-z])(?P<month>{_MONTH})\s+(?P<year>\d{{4}})\b", re.I)
RANGE_RE = re.compile(
    rf"(?P<start>{_MONTH_YEAR})\s*(?:to|–|—|-)\s*(?:(?:Expected|Anticipated)\s+)?"
    rf"(?P<end>{_MONTH_YEAR}|Present|Current|Now)\b",
    re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s|,;]+"
    r"|(?<![\w@.])(?:[\w-]+\.)+(?:com|io|dev|me|net|org|app|ai|co|us|edu)(?:/[^\s|,;]*)?(?![\w.])",
    re.I)
GPA_RE = re.compile(r"GPA:?\s*([0-4]\.\d+)", re.I)
SCHOOL_RE = re.compile(r"\b(?:University|College|Institute|School|Academy)\b")
_DEGREE_OF = (r"(?:\s+of\s+(?:Applied\s+Science|Science|Arts|Fine\s+Arts|Engineering"
              r"|Business\s+Administration))?")
DEGREE_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    rf"(?:Bachelor|Master|Associate)(?:['’]?s)?{_DEGREE_OF}"
    r"|B\.?Sc\.?|M\.?Sc\.?|M\.?B\.?A\.?|Ph\.?\s?D\.?|B\.?S\.?|B\.?A\.?|M\.?S\.?"
    r")(?![A-Za-z])")
BULLET_RE = re.compile(r"^\s*[•●▪◦‣∙·*\-–]\s*")
COLUMNS_RE = re.compile(r"\s{3,}")
SEGMENT_RE = re.compile(r"\s*[|•·]\s*|\s{3,}")
PROJECT_RE = re.compile(r"^(?P<name>[^()]+?)\s+[-–—]\s+(?P<rest>.+?)\s*\((?P<tech>[^)]+)\)\s*$")
LABEL_RE = re.compile(r"^(?P<label>[^:]{1,40}):\s*(?P<body>.*)$", re.S)
SKILL_PREFIX_RE = re.compile(r"^[A-Za-z][\w /&+-]{0,30}:\s*")
NAME_WORD_RE = re.compile(r"^[A-Z][A-Za-z.'’-]*$")

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
    r"(?P<state>[A-Z]{2}|[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\s*$")

_MONTH_NUMBERS = {name: i for i, name in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

COURSEWORK_SUGGESTION = "Add to Education"
CUSTOM_SUGGESTION = "Add as a custom field"


# ----- small helpers -----

def month_iso(text: str) -> str:
    """"June 2026" -> "2026-06-01"; "" when it isn't a month and year."""
    match = MONTH_YEAR_RE.search(text or "")
    if not match:
        return ""
    month = _MONTH_NUMBERS[match.group("month").lower()[:3]]
    return f"{match.group('year')}-{month:02d}-01"


def _clean(text: str) -> str:
    """Trims separators left behind after cutting dates or locations out of a line."""
    text = re.sub(r"\s{2,}", " ", text or "")
    return text.strip(" \t,;|–—-:")


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line)) and not PHONE_RE.match(line.strip())


def _unbullet(line: str) -> str:
    return BULLET_RE.sub("", line, count=1).strip()


def _location(text: str) -> tuple[str, str] | None:
    """(city, state) when `text` ends in "City, ST" or "City, State" (a US state)."""
    match = LOCATION_RE.search(text or "")
    if not match:
        return None
    state = match.group("state")
    if state not in US_STATES and state.lower() not in _STATE_NAMES:
        return None
    return match.group("city"), state


def _strip_location(text: str) -> tuple[str, str]:
    """Cuts a trailing "City, ST" off `text`: (rest, "City, ST")."""
    found = _location(text)
    if not found:
        return text, ""
    match = LOCATION_RE.search(text)
    rest = _clean(text[:match.start()])
    if not rest:  # the whole text is a place: leave it alone
        return text, ""
    return rest, f"{found[0]}, {found[1]}"


def _dates(text: str) -> dict:
    """{start, end, current} from a date range, or from single "Month YYYY"s."""
    rng = RANGE_RE.search(text or "")
    if rng:
        end_text = rng.group("end")
        current = end_text.lower() in ("present", "current", "now")
        return {"start": month_iso(rng.group("start")),
                "end": "" if current else month_iso(end_text), "current": current}
    months = [month_iso(m.group(0)) for m in MONTH_YEAR_RE.finditer(text or "")]
    if not months:
        return {"start": "", "end": "", "current": False}
    return {"start": months[0] if len(months) > 1 else "", "end": months[-1], "current": False}


def _has_dates(text: str) -> bool:
    return bool(RANGE_RE.search(text) or MONTH_YEAR_RE.search(text))


def split_line(line: str) -> tuple[str, str, str]:
    """A layout line -> (text, dates text, location).

    Columns are split on 3+ spaces; a right-hand date column is the dates, a column that is only
    a place is the location. Otherwise a date range inside the text is cut out of it.
    """
    cols = [c for c in COLUMNS_RE.split(line.strip()) if c]
    dates = ""
    location = ""
    if len(cols) > 1 and _has_dates(cols[-1]):
        dates = cols.pop()
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


def classify_header(header: str) -> str:
    """education|experience|projects|skills|coursework|custom, by the first header word."""
    known = set(konefal.resumeRead.KNOWN_HEADERS)
    for word in header.split():
        word = word.strip(":,.&").title()
        if word == "Education":
            return "education"
        if word == "Experience":
            return "experience"
        if word == "Projects":
            return "projects"
        if word == "Skills":
            return "skills"
        if word in ("Relevant", "Coursework"):
            return "coursework"
        if word in known:
            return "custom"
    return "custom"


def _header_title(header: str) -> str:
    header = header.strip().rstrip(":").strip()
    return header.title() if header.isupper() else header


# ----- contact info -----

def _segments(line: str) -> list[str]:
    return [s.strip() for s in SEGMENT_RE.split(line) if s and s.strip()]


def _contact_item(segment: str) -> bool:
    """True when the whole segment is an email, phone, URL or place."""
    segment = segment.strip()
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


def _url(text: str) -> str:
    text = text.rstrip(".")
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
            self.phone = phone.group(0).strip()
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
    for index, raw in enumerate(lines):
        line = _unbullet(raw)
        label, body = split_label(line)
        if label and re.search(r"coursework", label, re.I):
            entry["coursework"] = ", ".join(filter(None, [entry["coursework"], body]))
            continue
        text, dates, place = split_line(line)
        if dates:
            date_texts.append(dates)
        if place and not entry["location"]:
            entry["location"] = place
        used = bool(dates or place)
        gpa = GPA_RE.search(text)
        if gpa and not entry["gpa"]:
            entry["gpa"] = gpa.group(1)
            used = True
        degree = DEGREE_RE.search(text)
        if degree and not entry["degreeType"]:
            entry["degreeType"] = degree.group(0).strip()
            after = text[degree.end():]
            after = re.sub(r"^\s*(?:in|of)\s+", "", after.strip())
            after = re.split(r"\s*[,|(;]\s*|\s+[-–—]\s+|\s+GPA\b", after, maxsplit=1)[0]
            after = MONTH_YEAR_RE.split(after)[0] if MONTH_YEAR_RE.search(after) else after
            entry["major"] = _clean(after)
            used = True
        if not entry["school"] and (index == 0 or SCHOOL_RE.search(text)):
            parts = [p for p in re.split(r"\s+[-–—|]\s+|,\s*", text) if p.strip()]
            school = next((p for p in parts if SCHOOL_RE.search(p)), None)
            if school is None:
                school = next((p for p in parts if not DEGREE_RE.search(p)),
                              parts[0] if parts else "")
            entry["school"] = _clean(school)
            used = True
        if not dates:
            months = [m.group(0) for m in MONTH_YEAR_RE.finditer(text)]
            if months:
                date_texts.extend(months)
                used = True
        if not used and text:
            leftovers.append(line)
    if date_texts:
        found = _dates(" ".join(date_texts)) if len(date_texts) > 1 else _dates(date_texts[0])
        if len(date_texts) > 1 and not RANGE_RE.search(" ".join(date_texts)):
            months = [month_iso(t) for t in date_texts if month_iso(t)]
            found = {"start": months[0] if len(months) > 1 else "", "end": months[-1]}
        entry["start"], entry["end"] = found["start"], found["end"]
    if not entry["location"] and entry["school"]:
        entry["school"], entry["location"] = _strip_location(entry["school"])
    entry["location"] = entry["location"] or location
    return entry, leftovers


def _org_title(text: str) -> tuple[str, str]:
    """"Org - Title" or "Title, Org" or "Title at Org" -> (org, title)."""
    if re.search(r"\s+at\s+", text):
        title, org = re.split(r"\s+at\s+", text, maxsplit=1)
        return _clean(org), _clean(title)
    parts = re.split(r"\s+[-–—|]\s+", text, maxsplit=1)
    if len(parts) == 2:
        return _clean(parts[0]), _clean(parts[1])
    if "," in text:
        title, org = text.split(",", 1)
        return _clean(org), _clean(title)
    return _clean(text), ""


def parse_experience(lines: list[str]) -> dict:
    """One role's lines (head line, optional continuation lines, bullets) -> Experience sans id."""
    entry = {"title": "", "org": "", "location": "", "start": "", "end": "", "current": False,
             "detail": ""}
    detail: list[str] = []
    date_text = ""
    for index, raw in enumerate(lines):
        if _is_bullet(raw):
            detail.append(_unbullet(raw))
            continue
        text, dates, place = split_line(raw)
        date_text = date_text or dates
        if not dates and not date_text and MONTH_YEAR_RE.search(text):
            date_text = " ".join(m.group(0) for m in MONTH_YEAR_RE.finditer(text))
            text = _clean(MONTH_YEAR_RE.sub(" ", text))
        text, trailing_place = _strip_location(text)
        place = place or trailing_place
        if place and not entry["location"]:
            entry["location"] = place
        if index == 0:
            entry["org"], entry["title"] = _org_title(text)
        elif not text:
            continue
        elif not entry["title"]:
            entry["title"] = text
        elif not entry["location"] and _location(text):
            entry["location"] = text
        else:
            detail.append(text)
    if date_text:
        entry.update(_dates(date_text))
    entry["detail"] = "\n".join(d for d in detail if d)
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
        parts = re.split(r"\s+[-–—:]\s+|:\s+", text, maxsplit=1)
        entry["name"] = _clean(parts[0])
        if len(parts) == 2:
            detail.insert(0, _clean(parts[1]))
    entry["detail"] = "\n".join(d for d in detail if d)
    return entry


def parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        for col in COLUMNS_RE.split(_unbullet(raw)):
            col = SKILL_PREFIX_RE.sub("", col.strip())
            for item in re.split(r"\s*[,;|•·]\s*", col):
                item = SKILL_PREFIX_RE.sub("", item.strip()).rstrip(".").strip()  # "Tools: Git"
                if item and len(item) <= 40 and item.lower() not in seen:
                    seen.add(item.lower())
                    skills.append(item)
    return skills


def _tech_skills(projects: list[dict]) -> list[str]:
    return parse_skills([p["tech"] for p in projects if p.get("tech")])


def _starts_project(line: str) -> bool:
    text = COLUMNS_RE.split(line.strip())[0]
    return bool(re.search(r"\s[-–—|]\s|\||\(", text))


def _group(lines: list[str], starts_new) -> list[list[str]]:
    """Splits a section's lines into entries; `starts_new(line, group)` decides each boundary."""
    groups: list[list[str]] = []
    for line in lines:
        if not groups or (not _is_bullet(line) and starts_new(line, groups[-1])):
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def _new_experience(line: str, group: list[str]) -> bool:
    has_bullets = any(_is_bullet(g) for g in group)
    if has_bullets:
        return True
    group_dates = any(_has_dates(g) for g in group if not _is_bullet(g))
    return _has_dates(line) and group_dates


def _new_education(line: str, group: list[str]) -> bool:
    return bool(SCHOOL_RE.search(line)) and any(SCHOOL_RE.search(g) for g in group)


def _group_education(lines: list[str]) -> list[tuple[list[str], bool]]:
    """An Education section -> [(lines, same_school)], one entry per degree.

    A second degree line under one school ("Master of ..." then "Bachelor of ...") starts a new
    entry with `same_school` True: it takes its school from the entry before it.
    """
    groups: list[tuple[list[str], bool]] = []
    for line in lines:
        group = groups[-1][0] if groups else None
        if group is not None and _is_bullet(line):
            group.append(line)
        elif group is None or _new_education(line, group):
            groups.append(([line], False))
        elif DEGREE_RE.search(line) and any(DEGREE_RE.search(g) for g in group):
            groups.append(([line], True))
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


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def sections_to_profile(sections: dict[str, list[str]]) -> tuple[dict, list[dict], list[dict]]:
    """resumeRead sections -> (profile_patch, unplaced, labels). Pure; see the module doc."""
    contact = _Contact()
    edu_groups: list[tuple[list[str], bool]] = []
    exp_groups: list[list[str]] = []
    proj_groups: list[list[str]] = []
    skills_lines: list[str] = []
    has_skills_section = False
    unplaced: list[tuple[str, str | None]] = []

    for header, lines in (sections or {}).items():
        lines = [line for line in (lines or []) if line and line.strip()]
        if header == "Other":
            current: list[str] | None = None
            entries_started = False
            for line in lines:
                if current is not None and _is_bullet(line):
                    current.append(line)
                    continue
                if not contact.name and not entries_started and _is_name(line.strip()):
                    contact.name = line.strip() if not line.isupper() else line.strip().title()
                    continue
                if _is_contact_line(line, early=not entries_started):
                    contact.read(line)
                    continue
                kind = _classify_other(line)
                current = None
                if kind == "unplaced":
                    unplaced.append((_unbullet(line), None))
                    continue
                entries_started = True
                current = [line]
                if kind == "education":
                    edu_groups.append((current, False))
                else:
                    {"experience": exp_groups, "project": proj_groups}[kind].append(current)
            continue

        if not lines:
            continue
        kind = classify_header(header)
        if kind == "education":
            edu_groups.extend(_group_education(lines))
        elif kind == "experience":
            exp_groups.extend(_group(lines, _new_experience))
        elif kind == "projects":
            proj_groups.extend(_group(lines, _new_project))
        elif kind == "skills":
            has_skills_section = True
            skills_lines.extend(lines)
        else:
            separator = " " if kind == "coursework" else "; "
            body = separator.join(_unbullet(line) for line in lines)
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
    experience = [{"id": f"x-{n}", **parse_experience(g)} for n, g in enumerate(exp_groups, 1)]
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
        sections = konefal.read_resume(path)
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
