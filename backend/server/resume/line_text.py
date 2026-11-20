"""Small text helpers for one resume line: bullets, indents, separators and labels."""
import re

from server.resume.patterns import BULLET_RE, LABEL_RE, PHONE_RE


def clean(text: str) -> str:
    """Return `text` without the separators left behind after cutting dates or places out."""
    text = re.sub(r"\s{2,}", " ", text or "")
    return text.strip(" \t,;|–—-:·•◆/@")


def is_bullet(line: str) -> bool:
    """Return True when the line starts with a bullet glyph (a phone number's "-" isn't one)."""
    return bool(BULLET_RE.match(line)) and not PHONE_RE.match(line.strip())


def unbullet(line: str) -> str:
    """Return the line without its leading bullet glyph."""
    return BULLET_RE.sub("", line, count=1).strip()


def indent(line: str) -> int:
    """Return how many blank characters the line starts with."""
    return len(line) - len(line.lstrip())


def split_label(text: str) -> tuple[str | None, str]:
    """Split "Relevant Coursework: A, B" into ("Relevant Coursework", "A, B"), else (None, text)."""
    match = LABEL_RE.match(text or "")
    if match and len(match.group("label").split()) <= 4:
        return match.group("label").strip(), match.group("body").strip()
    return None, text
