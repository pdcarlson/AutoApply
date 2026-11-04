import os

from pypdf import PdfReader


def readResume(path):
    if not os.path.exists(path):
        print("No such file or directory")
        return None
    if path.endswith(".pdf"):
        return readResumePDF(path)

    pass


def readResumePDF(pdf_path):
    # creating a pdf reader object
    reader = PdfReader(pdf_path)

    # printing number of pages in pdf file
    print(len(reader.pages))

    # creating a page object
    text = []
    #create a dictionary: headers as keys, else as value for most recent key
    sections = {"Other": []}
    curKey = "Other"
    for page in reader.pages:
        page_text = page.extract_text(extraction_mode="layout")
        words = page_text.split(sep="\n")
        for word in words:
            word.strip()
            if word == "" or word == ",":
                continue
            text.append(word)
    print(text[1])
    return text
