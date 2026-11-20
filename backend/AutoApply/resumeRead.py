import os

import docx
from pypdf import PdfReader
from docx import *

MAX_FILE_SIZE = 3*2**8  # look into a good max file size
MAX_HEADER_WORDS = 3
KNOWN_HEADERS = ["Education", "Experience", "Service", "Hobbies", "Projects",
                 "Skills", "Awards", "Honors", "Relevant", "Coursework",
                 "Certifications", "Activities", "Leadership", "Summary",
                 "Objective", "Publications", "Volunteer"]


def isHeader(text):
    words = text.split()
    headWord = False
    for word in words:
        if word in KNOWN_HEADERS:
            headWord = True
            break
    return 1 <= len(words) <= MAX_HEADER_WORDS and headWord


def readResume(path):
    if not os.path.exists(path):
        print("No such file or directory")
        return None
    if path.endswith(".pdf"):
        return readResumePDF(path)
    if path.endswith(".docx"):
        print("docx support not yet implemented.")
        return None
    pass


def readResumePDF(pdf_path):
    # creating a pdf reader object
    reader = PdfReader(pdf_path)

    # check if the file is too short or too long - someone may be messing with us
    if len(reader.pages) == 0 or len(reader.pages) > 15:
        print("File not valid")
        return None

    # create a dictionary: headers as keys, else as value for most recent key
    sections = {"Other": []}
    curKey = "Other"

    for page in reader.pages:
        for line in page.extract_text(extraction_mode="layout").split("\n"):
            line = line.strip()
            if not line:
                continue

            if isHeader(line):
                curKey = line
                sections.setdefault(curKey, [])
            else:
                sections[curKey].append(line)
    return sections


def readResumeDOCX(docx_path):
    doc = docx.Document(docx_path)

    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)

    # create a dictionary: headers as keys, else as value for most recent key
    sections = {"Other": []}
    curKey = "Other"

    for paragraph in doc.paragraphs:
        line = paragraph.text
        line.strip()
        if not line:
            continue
        if isHeader(line) or paragraph.style.name.startswith("Heading") or paragraph.style.name == "Title":
            curKey = line
            sections.setdefault(curKey, [])
        else:
            sections[curKey].append(line)
    return sections


def file_size_check():
    pass
