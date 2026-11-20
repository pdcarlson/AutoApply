"""Reads a PDF or DOCX resume into `{header: [lines]}` sections, "Other" first."""
from pathlib import Path

from server import onboarding_modules
from server.resume.columns import Chunk, page_chunks
from server.resume.pdf_lines import clean_line
from server.resume.section_headers import header_name

OPENING_SECTION = "Other"


def read_resume(path: Path | str) -> dict[str, list[str]] | None:
    """Return the resume's sections, or None if it has no text."""
    if str(path).lower().endswith(".pdf") and Path(path).exists():
        return pdf_sections(path)
    # DOCX files go through the onboarding module's reader; its sections are re-split here
    sections = onboarding_modules.read_resume(path)
    return resection(sections) if sections else None


def pdf_sections(path: Path | str) -> dict[str, list[str]] | None:
    """Return a PDF's sections, read page by page with its columns untangled."""
    # pypdf is slow to import and only needed once a PDF arrives
    from pypdf import PdfReader  # pylint: disable=import-outside-toplevel
    chunks: list[Chunk] = []
    for page in PdfReader(str(path)).pages:
        chunks.extend(page_chunks(page.extract_text(extraction_mode="layout").split("\n")))
    if not any(line.strip() for lines, _ in chunks for line in lines):
        return None
    return sections_from_chunks(chunks)


def sections_from_chunks(chunks: list[Chunk]) -> dict[str, list[str]]:
    """Return the chunks' lines split into sections at each header."""
    sections: dict[str, list[str]] = {OPENING_SECTION: []}
    key = OPENING_SECTION
    for lines, starts_outside in chunks:
        if starts_outside:
            key = OPENING_SECTION
        for line in lines:
            name = header_name(line)
            if name:
                key = name
                sections.setdefault(key, [])
            elif line.strip():
                sections[key].append(line.rstrip())
    return sections


def resection(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """Return another reader's sections re-split with this package's headers."""
    lines: list[str] = []
    for header, body in sections.items():
        if header != OPENING_SECTION:
            lines.append(header)
        lines.extend(body)
    return sections_from_chunks([([clean_line(line) for line in lines], False)])
