import os

from pypdf import PdfReader

MAX_HEADER_WORDS = 3
KNOWN_HEADERS = ["Education", "Experience", "Service", "Hobbies", "Projects",
                 "Skills", "Awards", "Honors", "Relevant", "Coursework",
                 "Certifications", "Activities", "Leadership", "Summary",
                 "Objective", "Publications", "Volunteer",]


def isHeader(text):
    words = text.split()
    headWord = False
    for word in words:
        # case-insensitive, and "Skills:" counts as "Skills"
        if word.strip(":,.").title() in KNOWN_HEADERS:
            headWord = True
            break
    return 1 <= len(words) <= MAX_HEADER_WORDS and headWord


def readResume(path):
    if not os.path.exists(path):
        print("No such file or directory")
        return None
    if path.lower().endswith(".pdf"):
        return readResumePDF(path)
    if path.lower().endswith(".docx"):
        return readResumeDOCX(path)
    return None


def sectionsFromLines(lines):
    # create a dictionary: headers as keys, else as value for most recent key
    sections = {"Other": []}
    curKey = "Other"
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if isHeader(line):
            curKey = line
            sections.setdefault(curKey, [])
        else:
            sections[curKey].append(line)
    return sections


def readResumePDF(pdf_path):
    # creating a pdf reader object
    reader = PdfReader(pdf_path)

    lines = []
    for page in reader.pages:
        lines.extend(page.extract_text(extraction_mode="layout").split("\n"))

    # no text at all (e.g. a scanned resume)
    if not any(line.strip() for line in lines):
        return None
    return sectionsFromLines(lines)


def readResumeDOCX(docx_path):
    # imported here so the PDF path works without python-docx installed
    import docx
    from docx.table import Table

    document = docx.Document(docx_path)
    lines = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = []
                for cell in row.cells:
                    text = cell.text.strip()
                    if text and text not in cells:  # merged cells repeat their text
                        cells.append(text)
                if all("\n" not in text for text in cells):
                    # one line per row; 3+ spaces between cells, like PDF layout columns
                    lines.append("   ".join(cells))
                else:
                    for text in cells:
                        lines.extend(text.split("\n"))
        else:
            lines.extend(block.text.split("\n"))

    if not any(line.strip() for line in lines):
        return None
    return sectionsFromLines(lines)


def pageCount(path):
    # number of pages for a PDF, None for anything else (or an unreadable file)
    if not path.lower().endswith(".pdf"):
        return None
    try:
        return len(PdfReader(path).pages)
    except Exception:  # pylint: disable=broad-except
        return None
