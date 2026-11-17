"""Resume file -> `{header: [lines]}` sections, ready for `resume_import.sections_to_profile`.

resumeRead (spec 1.3) reads PDFs line by line across the whole page, which mixes up two-column
layouts: a sidebar's "Skills" list ends up glued to the main column's job lines. This module reads
the same pypdf layout text, but first finds column gutters (a band of blank characters that runs
down a block of lines) and decides what each column is:

- both columns have section headers (a sidebar resume): read the wider column, then the other;
- only the left column has headers (a "label" column, as in table-style resumes): put each label
  on its own line before the text beside it;
- otherwise (a column of dates, or a skills table): leave the lines alone.

Headers are matched against a vocabulary of section words, after undoing letter-spaced and
PDF-split headers ("E D U C A T I O N", "EXPERIE NCE").

DOCX files still go through resumeRead's reader; its sections are re-split with these headers.
"""
import re
from functools import lru_cache
from pathlib import Path

from server import konefal

# ----- header vocabulary -----

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
_VOCAB = HEADER_WORDS | HEADER_MODIFIERS
_DECOR_RE = re.compile(r"^[\s—–\-_=~•●▪■◆◇#*>|]+|[\s—–\-_=~•●▪■◆◇#*<|:]+$")
_SHELL_RE = re.compile(r"^\s*(?:\$|#|>)\s+")  # "$ cat skills.yaml": a terminal-style header


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+|&|\+", text)


def _vocab_header(words: list[str]) -> bool:
    low = [w.lower() for w in words]
    if not low or len(low) > 6 or not any(w in HEADER_WORDS for w in low):
        return False
    if all(w in _VOCAB for w in low):
        return True
    return len(low) <= 2 and low[-1] in _LOOSE_LAST


@lru_cache(maxsize=None)
def _segment(letters: str) -> tuple[str, ...] | None:
    """"TECHNICALSKILLS" -> ("TECHNICAL", "SKILLS"): the run split into vocabulary words."""
    if not letters:
        return ()
    for end in range(len(letters), 0, -1):
        head = letters[:end]
        if head.lower() in _VOCAB:
            rest = _segment(letters[end:])
            if rest is not None:
                return (head, *rest)
    return None


def unspace(line: str) -> str:
    """"E D U C AT I O N" -> "EDUCATION"; "C R I T I C A L   C A R E" -> "CRITICAL CARE".

    Letter-spaced text puts one space between letters and two or more between words. Lines that
    aren't letter-spaced come back unchanged.
    """
    # Each column (split on wide gaps) is checked on its own, so a letter-spaced header beside
    # ordinary text ("E X P E R I E N C E      Project Architect") only joins the header.
    out = []
    for part in re.split(r"(\s{5,})", line):
        tokens = part.split()
        singles = sum(len(t) == 1 and t.isalpha() for t in tokens)
        if part.isspace() or len(tokens) < 4 or singles < 0.5 * len(tokens):
            out.append(part)
            continue
        words = [w.replace(" ", "") for w in re.split(r"\s{2,}", part.strip())]
        lead = part[:len(part) - len(part.lstrip())]
        # pad to the old width so a column to the right stays where it was
        out.append((lead + " ".join(w for w in words if w)).ljust(len(part)))
    return "".join(out)


def header_name(line: str) -> str | None:
    """The header text if `line` is a section header, else None."""
    text = line.strip()
    if not text or len(text) > 60 or re.search(r"[\d@]", text):
        return None
    shell = bool(_SHELL_RE.match(text))
    if shell:  # "$ ls ./experience --sort=date" or "$ cat education.txt certs.txt"
        words = [w for w in _words(text) if w.lower() in HEADER_WORDS]
        return words[0].title() if words else None
    if re.search(r":\s*\S", text) or text.endswith((".", ",")):
        return None  # "Languages: Go, Python" is a skills line, not a header
    text = _DECOR_RE.sub("", text).strip()
    small = {"of", "and", "in", "the", "&", "+"}
    if not text or any(w[0].islower() for w in _words(text) if w not in small):
        return None  # headers are Title Case or UPPER CASE: "Executive presentations" isn't one
    candidates = [text, unspace(text)]
    letters = re.sub(r"[^A-Za-z&]", "", text)
    if text.upper() == text and letters:
        found = _segment(letters)
        if found:
            candidates.append(" ".join(found))
    for candidate in candidates:
        if _vocab_header(_words(candidate)):
            return re.sub(r"\s+", " ", candidate).strip()
    return None


# ----- line clean-up -----

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
# pypdf's layout mode mis-measures ligature glyphs and leaves a gap after them: "Certiﬁc   ate",
# "oﬃ  ce", "ﬁ nancial". Rejoin a gap that follows a lone ligature, or a wide gap before a short
# word fragment. A single space before a whole word ("staﬀ auditors") is a real space.
_LIGATURE_GAP_RE = re.compile(r"(?:(?<![A-Za-z])([ﬀ-ﬆ]) +(?=[a-z])"
                              r"|([ﬀ-ﬆ][a-z]*) {2,}(?=[a-z]{1,4}\b))")
_FOOTER_RE = re.compile(r"^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$", re.I)


def clean_line(line: str) -> str:
    """Undoes PDF text quirks: ligatures, non-breaking spaces, icon-font glyphs, letter-spacing."""
    if _FOOTER_RE.match(line):
        return ""
    # Icon fonts use the Private Use Area (a "·" or "–" drawn as an icon); a space keeps columns
    line = re.sub(r"[-   ]", " ", line)
    line = _LIGATURE_GAP_RE.sub(lambda m: m.group(1) or m.group(2), line)
    for glyph, text in _LIGATURES.items():
        line = line.replace(glyph, text)
    return unspace(line.rstrip()) if line.strip() else ""


# ----- columns -----

def _find_block(lines: list[str], start: int,  # pylint: disable=too-many-locals,too-many-branches
                width: int) -> tuple[int, int, int] | None:
    """The longest run of lines from `start` that shares a blank gutter: (end, gap, column).

    A gutter is 3+ blank characters, in every line, with text on its left in 2+ lines and text on
    its right in 2+ lines. `gap` is where the blank band starts, `column` where it ends.
    """
    blank = [True] * width
    first = [len(l) - len(l.lstrip()) for l in lines]
    ends = [len(l) for l in lines]
    best = None
    for j in range(start, len(lines)):
        line = lines[j]
        for c, char in enumerate(line[:width]):
            if char != " ":
                blank[c] = False
        runs = []
        c = 3
        while c < width:
            if blank[c]:
                d = c
                while d < width and blank[d]:
                    d += 1
                if d - c >= 3 and d < width:
                    runs.append((c, d))
                c = d
            else:
                c += 1
        if not runs:
            break
        if j - start < 2:
            continue
        scored = []
        for gap, column in runs:
            left = sum(first[k] < gap for k in range(start, j + 1))
            right = sum(ends[k] > column for k in range(start, j + 1))
            if left >= 2 and right >= 2:
                scored.append((min(left, right), column - gap, gap, column))
        if scored:
            _, _, gap, column = max(scored)
            best = (j + 1, gap, column)
    return best


def _dedent(parts: list[str]) -> list[str]:
    indents = [len(p) - len(p.lstrip()) for p in parts if p.strip()]
    cut = min(indents) if indents else 0
    return [p[cut:].rstrip() for p in parts]


def _emit_block(block: list[str], gap: int, column: int) -> list[tuple[list[str], bool]]:
    """One gutter block -> chunks of lines; a chunk with True starts outside any section."""
    left = [l[:gap].rstrip() for l in block]
    right = _dedent([l[column:] if len(l) > column else "" for l in block])
    left_cells = [p for p in left if p.strip()]
    left_headers = sum(bool(header_name(p)) for p in left_cells)
    right_headers = any(header_name(p) for p in right if p.strip())
    if left_headers and right_headers:  # a sidebar: two separate streams, main one first
        streams = [[p for p in left if p.strip()], [p for p in right if p.strip()]]
        streams.sort(key=lambda s: -sum(len(p.strip()) for p in s))
        return [(s, True) for s in streams]
    # a label column: "EXPERIENCE   Senior Engineer ..."
    if left_cells and left_headers >= 0.6 * len(left_cells):
        rows: list[str] = []
        for l_part, r_part in zip(left, right):
            rows.extend(p for p in (l_part, r_part) if p.strip())
        return [(rows, False)]
    return [(block, False)]


def page_chunks(lines: list[str]) -> list[tuple[list[str], bool]]:
    """One page's layout lines -> chunks with columns untangled (see the module doc)."""
    lines = [clean_line(l) for l in lines]
    lines = [l for l in lines if l.strip() and not _FOOTER_RE.match(l)]
    if not lines:
        return []
    width = max(len(l) for l in lines) + 1
    # Only blocks that change something (sidebars, label columns) count; a column of dates
    # is read as it is. Longest first, so a small block can't cut a sidebar in two.
    blocks = []
    for start in range(len(lines)):
        found = _find_block(lines, start, width)
        if found and found[0] - start >= 3:
            emitted = _emit_block(lines[start:found[0]], found[1], found[2])
            if emitted != [(lines[start:found[0]], False)]:
                blocks.append((found[0] - start, start, found[0], emitted))
    taken = [False] * len(lines)
    chosen = []
    for _, start, end, emitted in sorted(blocks, key=lambda b: (-b[0], b[1])):
        if not any(taken[start:end]):
            taken[start:end] = [True] * (end - start)
            chosen.append((start, end, emitted))
    chosen.sort(key=lambda c: c[0])
    chunks: list[tuple[list[str], bool]] = []
    plain: list[str] = []
    i = 0
    for start, end, emitted in chosen:
        plain.extend(lines[i:start])
        if plain:
            chunks.append((plain, False))
            plain = []
        chunks.extend(emitted)
        i = end
    plain.extend(lines[i:])
    if plain:
        chunks.append((plain, False))
    return chunks


# ----- sections -----

def sections_from_chunks(chunks: list[tuple[list[str], bool]]) -> dict[str, list[str]]:
    """Chunks of lines -> `{header: [lines]}` with "Other" first, like resumeRead."""
    sections: dict[str, list[str]] = {"Other": []}
    key = "Other"
    for lines, reset in chunks:
        if reset:
            key = "Other"
        for line in lines:
            name = header_name(line)
            if name:
                key = name
                sections.setdefault(key, [])
            elif line.strip():
                sections[key].append(line.rstrip())
    return sections


def pdf_sections(path: Path | str) -> dict[str, list[str]] | None:
    """`{header: [lines]}` for a PDF, read page by page with its columns untangled."""
    from pypdf import PdfReader  # pylint: disable=import-outside-toplevel
    chunks: list[tuple[list[str], bool]] = []
    for page in PdfReader(str(path)).pages:
        chunks.extend(page_chunks(page.extract_text(extraction_mode="layout").split("\n")))
    if not any(line.strip() for lines, _ in chunks for line in lines):
        return None
    return sections_from_chunks(chunks)


def resection(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """Re-splits resumeRead's sections with this module's headers (for DOCX files)."""
    lines: list[str] = []
    for header, body in sections.items():
        if header != "Other":
            lines.append(header)
        lines.extend(body)
    return sections_from_chunks([([clean_line(l) for l in lines], False)])


def read_resume(path: Path | str) -> dict[str, list[str]] | None:
    """`{header: [lines]}` for a PDF or DOCX resume, or None if it has no text."""
    if str(path).lower().endswith(".pdf") and Path(path).exists():
        return pdf_sections(path)
    sections = konefal.read_resume(path)
    return resection(sections) if sections else None
