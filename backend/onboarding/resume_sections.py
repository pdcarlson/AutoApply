"""Reads a PDF or DOCX resume into `{header: [lines]}` sections, "Other" first."""
import logging
from pathlib import Path

from pypdf import PdfReader

log = logging.getLogger(__name__)

OPENING_SECTION = "Other"
MAX_HEADER_WORDS = 3
MAX_PDF_PAGES = 15
KNOWN_HEADERS = ["Education", "Experience", "Service", "Hobbies", "Projects",
                 "Skills", "Awards", "Honors", "Relevant", "Coursework",
                 "Certifications", "Activities", "Leadership", "Summary",
                 "Objective", "Publications", "Volunteer"]
# Table cells on one row are joined like the column gaps in PDF layout text
CELL_GAP = "   "


def read_resume(path: Path | str) -> dict[str, list[str]] | None:
    """Return the resume's sections, or None if the file is missing, unsupported or blank."""
    path = Path(path)
    if not path.exists():
        log.warning("No resume file at %s", path)
        return None
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    return None


def page_count(path: Path | str) -> int | None:
    """Return how many pages a PDF has, or None for other files and unreadable PDFs."""
    if Path(path).suffix.lower() != ".pdf":
        return None
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:  # pylint: disable=broad-except  # pypdf raises many types on a broken file
        return None


def is_header(text: str) -> bool:
    """Return True for a short line that names a known section, in any case ("SKILLS:")."""
    words = text.split()
    names_section = any(word.strip(":,.").title() in KNOWN_HEADERS for word in words)
    return 1 <= len(words) <= MAX_HEADER_WORDS and names_section


def sections_from_lines(lines: list[str]) -> dict[str, list[str]]:
    """Return the lines grouped under the header above them."""
    sections: dict[str, list[str]] = {OPENING_SECTION: []}
    key = OPENING_SECTION
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if is_header(line):
            key = line
            sections.setdefault(key, [])
        else:
            sections[key].append(line)
    return sections


def _read_pdf(path: Path) -> dict[str, list[str]] | None:
    """Return a PDF's sections, or None if it has no text or a suspicious page count."""
    reader = PdfReader(str(path))
    if not reader.pages or len(reader.pages) > MAX_PDF_PAGES:
        log.warning("Rejected a resume PDF with %d pages", len(reader.pages))
        return None
    lines = []
    for page in reader.pages:
        lines.extend(page.extract_text(extraction_mode="layout").split("\n"))
    # A scanned resume has pages but no text
    if not any(line.strip() for line in lines):
        return None
    return sections_from_lines(lines)


def _read_docx(path: Path) -> dict[str, list[str]] | None:
    """Return a DOCX's sections, with each simple table row read as one line."""
    # Imported here so reading PDFs works without python-docx installed
    import docx  # pylint: disable=import-outside-toplevel
    from docx.table import Table  # pylint: disable=import-outside-toplevel

    lines = []
    for block in docx.Document(str(path)).iter_inner_content():
        if isinstance(block, Table):
            lines.extend(_table_lines(block))
        else:
            lines.extend(block.text.split("\n"))
    if not any(line.strip() for line in lines):
        return None
    return sections_from_lines(lines)


def _table_lines(table) -> list[str]:
    """Return a DOCX table as text lines: one per row, unless a cell holds several lines."""
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip()
            # Merged cells repeat their text once per grid cell they cover
            if text and text not in cells:
                cells.append(text)
        if all("\n" not in text for text in cells):
            lines.append(CELL_GAP.join(cells))
        else:
            for text in cells:
                lines.extend(text.split("\n"))
    return lines
