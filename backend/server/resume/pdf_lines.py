"""Undoes the quirks of text extracted from a PDF, one line at a time."""
import re

from server.resume.section_headers import unspace

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
# pypdf's layout mode mis-measures ligature glyphs and leaves a gap after them: "Certiﬁc   ate",
# "oﬃ  ce", "ﬁ nancial". Rejoin a gap that follows a lone ligature, or a wide gap before a short
# word fragment. A single space before a whole word ("staﬀ auditors") is a real space.
_LIGATURE_GAP_RE = re.compile(r"(?:(?<![A-Za-z])([ﬀ-ﬆ]) +(?=[a-z])"
                              r"|([ﬀ-ﬆ][a-z]*) {2,}(?=[a-z]{1,4}\b))")
FOOTER_RE = re.compile(r"^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$", re.I)


def clean_line(line: str) -> str:
    """Return the line without ligatures, odd spaces, icon-font glyphs or letter-spacing."""
    if FOOTER_RE.match(line):
        return ""
    # Icon fonts use the Private Use Area (a "·" or "–" drawn as an icon), and PDFs use odd
    # spaces (no-break, figure, narrow); a plain space in their place keeps the columns
    line = re.sub(r"[-   ]", " ", line)
    line = _LIGATURE_GAP_RE.sub(lambda match: match.group(1) or match.group(2), line)
    for glyph, text in _LIGATURES.items():
        line = line.replace(glyph, text)
    return unspace(line.rstrip()) if line.strip() else ""
