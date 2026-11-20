"""Reads a resume's skills lists into a list of skills."""
import re

from server.resume.entries import ProjectEntry
from server.resume.line_text import unbullet
from server.resume.patterns import COLUMNS_RE, SKILL_PREFIX_RE

SPOKEN_RE = re.compile(r"\b(?:native|fluent|conversational|bilingual|proficien\w*|intermediate"
                       r"|elementary|professional|[ABC][12]|English|Spanish|French|German"
                       r"|Mandarin|Chinese|Hindi|Arabic|Portuguese|Japanese|Korean|Italian"
                       r"|Russian|Tagalog|Bengali|Dutch|Vietnamese|Urdu)\b", re.I)
_ITEM_SEPARATORS = ",;|•·◆▪✓"
_MAX_SKILL_CHARACTERS = 40
_MAX_SKILL_WORDS = 5


def glue_skill_lines(lines: list[str]) -> list[str]:
    """Rejoin a skills list that wrapped: "Microsoft" then "365 · Miro", "(advanced" then
    "modeling)", "Hemodynamic monitoring" then "(arterial lines, PA catheters)"."""
    glued: list[str] = []
    for raw in lines:
        text = raw.strip()
        if glued and text and _continues_skill_line(text, glued[-1]):
            glued[-1] = f"{glued[-1].rstrip()} {text}"
        else:
            glued.append(raw)
    return glued


def _continues_skill_line(text: str, previous: str) -> bool:
    """Return True when `text` is the wrapped rest of the skills line before it."""
    if re.match(r"^[\w ]{1,20}:", text):  # "containers:  [Kubernetes, EKS]"
        return False
    return (text[0].islower() or text[0].isdigit() or text[0] == "("
            or previous.count("(") > previous.count(")"))


def parse_skills(lines: list[str]) -> list[str]:
    """Return every distinct skill named in the lines, in order."""
    skills: list[str] = []
    seen: set[str] = set()
    for raw in glue_skill_lines(lines):
        line = unbullet(raw)
        if _is_subheading(line):
            continue
        for column in _skill_columns(line):
            column = SKILL_PREFIX_RE.sub("", column.strip()).strip("[] ")
            for item in _split_items(column):
                item = SKILL_PREFIX_RE.sub("", item.strip()).strip("[] ").rstrip(".").strip()
                if _is_skill(item) and item.lower() not in seen:
                    seen.add(item.lower())
                    skills.append(item)
    return skills


def _is_subheading(line: str) -> bool:
    """Return True for a sub-heading like "ML & STATS" inside a skills section."""
    return (line.isupper() and ("&" in line or len(line.split()) > 1)
            and not re.search(r"[,·•]", line))


def _skill_columns(line: str) -> list[str]:
    """Return the line's columns, without a label column ("CAD / PLM      CATIA V5, ...")."""
    columns = [column for column in COLUMNS_RE.split(line) if column.strip()]
    if (len(columns) > 1 and len(columns[0].split()) <= 3 and "," not in columns[0]
            and re.search(r"[,·•]", " ".join(columns[1:]))):
        columns = columns[1:]
    return [piece for column in columns for piece in re.split(r"\s{2,}", column.strip())]


def _is_skill(item: str) -> bool:
    """Return True for a short item with letters in it; a note in parentheses doesn't count."""
    bare = re.sub(r"\([^)]*\)", "", item)  # "Hemodynamic monitoring (arterial ...)"
    return bool(item and len(bare) <= _MAX_SKILL_CHARACTERS
                and len(bare.split()) <= _MAX_SKILL_WORDS and re.search(r"[A-Za-z]", item))


def _split_items(text: str) -> list[str]:
    """Split a skills line on , ; | • · and the like, but not inside parentheses."""
    items, depth, current = [], 0, ""
    for char in text:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth <= 0 and char in _ITEM_SEPARATORS:
            items.append(current)
            current = ""
            depth = 0
        else:
            current += char
    items.append(current)
    return items


def is_prose(lines: list[str]) -> bool:
    """Return True when most lines are sentences, not lists (a functional resume's "skills")."""
    cells = [unbullet(cell) for line in lines for cell in COLUMNS_RE.split(line.strip())
             if cell.strip()]
    sentences = [cell for cell in cells
                 if len(cell.split()) >= 5 and len(re.findall(r"[,;·•|]", cell)) < 2]
    return len(sentences) >= 0.4 * len(cells)


def skills_from_projects(projects: list[ProjectEntry]) -> list[str]:
    """Return the skills named in the projects' tech lists."""
    return parse_skills([project.tech for project in projects if project.tech])
