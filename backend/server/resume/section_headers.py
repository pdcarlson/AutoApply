"""Recognizes a resume's section headers ("Experience", "TECHNICAL SKILLS", "E D U C A T I O N")."""
import re
from functools import lru_cache

# Words that make a line a section header on their own ("Experience", "TECHNICAL SKILLS").
HEADER_WORDS = {
    "education", "experience", "experiences", "employment", "career", "timeline", "history",
    "projects", "skills", "competencies", "expertise", "proficiencies", "technologies", "tools",
    "toolkit", "software", "summary", "profile", "objective", "about", "overview", "contact",
    "certifications", "certificates", "certification", "licenses", "license", "licensure",
    "credentials", "awards", "honors", "achievements", "accomplishments", "publications",
    "presentations", "talks", "speaking", "research", "teaching", "volunteer", "volunteering",
    "service", "community", "outreach", "leadership", "activities", "involvement",
    "extracurriculars", "extracurricular", "interests", "hobbies", "languages", "references",
    "affiliations", "memberships", "coursework", "training", "qualifications", "fellowships",
    "grants", "patents", "extras", "boards", "highlights", "strengths",
}
# Words that only qualify a header word ("Professional", "Areas of").
HEADER_MODIFIERS = {
    "professional", "relevant", "technical", "core", "key", "selected", "select", "additional",
    "other", "academic", "related", "work", "areas", "of", "and", "in", "the", "signature",
    "spoken", "personal", "notable", "recent", "conference", "clinical", "military", "industry",
    "international", "programming", "digital", "creative", "social", "executive", "skill",
    "technology", "project", "honor", "&", "+", "/",
}
# A header of one or two words whose last word is one of these ("Sales Skills").
_LOOSE_LAST = {"skills", "experience", "education", "projects", "history", "summary",
               "certifications", "awards", "publications"}
_VOCABULARY = HEADER_WORDS | HEADER_MODIFIERS
_SMALL_WORDS = {"of", "and", "in", "the", "&", "+"}
_DECORATION_RE = re.compile(r"^[\s—–\-_=~•●▪■◆◇#*>|]+|[\s—–\-_=~•●▪■◆◇#*<|:]+$")
_SHELL_RE = re.compile(r"^\s*(?:\$|#|>)\s+")  # "$ cat skills.yaml": a terminal-style header


def _words(text: str) -> list[str]:
    """Return the words of `text`, counting "&" and "+" as words."""
    return re.findall(r"[A-Za-z]+|&|\+", text)


def _is_vocabulary_header(words: list[str]) -> bool:
    """Return True when the words make up a header from the vocabulary."""
    lowered = [word.lower() for word in words]
    if not lowered or len(lowered) > 6 or not any(word in HEADER_WORDS for word in lowered):
        return False
    if all(word in _VOCABULARY for word in lowered):
        return True
    return len(lowered) <= 2 and lowered[-1] in _LOOSE_LAST


@lru_cache(maxsize=None)
def _segment(letters: str) -> tuple[str, ...] | None:
    """Split a run of letters into vocabulary words ("TECHNICALSKILLS"), or return None."""
    if not letters:
        return ()
    for end in range(len(letters), 0, -1):
        head = letters[:end]
        if head.lower() in _VOCABULARY:
            rest = _segment(letters[end:])
            if rest is not None:
                return (head, *rest)
    return None


def unspace(line: str) -> str:
    """Undo letter-spacing: "E D U C AT I O N" -> "EDUCATION", "C R I T I C A L   C A R E" ->
    "CRITICAL CARE"; other lines come back unchanged."""
    # Each column (split on wide gaps) is checked on its own, so a letter-spaced header beside
    # ordinary text ("E X P E R I E N C E      Project Architect") only joins the header.
    out = []
    for part in re.split(r"(\s{5,})", line):
        tokens = part.split()
        singles = sum(len(token) == 1 and token.isalpha() for token in tokens)
        if part.isspace() or len(tokens) < 4 or singles < 0.5 * len(tokens):
            out.append(part)
            continue
        # one space between letters, two or more between words
        words = [word.replace(" ", "") for word in re.split(r"\s{2,}", part.strip())]
        lead = part[:len(part) - len(part.lstrip())]
        # pad to the old width so a column to the right stays where it was
        out.append((lead + " ".join(word for word in words if word)).ljust(len(part)))
    return "".join(out)


def header_name(line: str) -> str | None:
    """Return the header text if `line` is a section header, else None."""
    text = line.strip()
    if not text or len(text) > 60 or re.search(r"[\d@]", text):
        return None
    if _SHELL_RE.match(text):  # "$ ls ./experience --sort=date" or "$ cat education.txt"
        words = [word for word in _words(text) if word.lower() in HEADER_WORDS]
        return words[0].title() if words else None
    if re.search(r":\s*\S", text) or text.endswith((".", ",")):
        return None  # "Languages: Go, Python" is a skills line, not a header
    text = _DECORATION_RE.sub("", text).strip()
    if not text or any(word[0].islower() for word in _words(text) if word not in _SMALL_WORDS):
        return None  # headers are Title Case or UPPER CASE: "Executive presentations" isn't one
    for candidate in _candidates(text):
        if _is_vocabulary_header(_words(candidate)):
            return re.sub(r"\s+", " ", candidate).strip()
    return None


def _candidates(text: str) -> list[str]:
    """Return the ways to read a header: as written, unspaced, and split into words."""
    candidates = [text, unspace(text)]
    letters = re.sub(r"[^A-Za-z&]", "", text)
    if text.upper() == text and letters:
        found = _segment(letters)
        if found:
            candidates.append(" ".join(found))
    return candidates
