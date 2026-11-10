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

    # printing number of pages in pdf file
    # print(len(reader.pages))

    # creating a page object
    text = []

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
