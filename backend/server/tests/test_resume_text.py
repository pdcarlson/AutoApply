"""Resume reading: headers, PDF text clean-up and column untangling, on layout lines."""
import pytest

from server.resume.columns import page_chunks
from server.resume.pdf_lines import clean_line
from server.resume.resume_reader import sections_from_chunks
from server.resume.section_headers import header_name


@pytest.mark.parametrize("line, header", [
    ("Experience", "Experience"),
    ("PROFESSIONAL EXPERIENCE", "PROFESSIONAL EXPERIENCE"),
    ("E D U C AT I O N", "EDUCATION"),                   # letter-spaced
    ("P R O F E S S I O N A L  S U M M A RY", "PROFESSIONAL SUMMARY"),
    ("EXPERIE NCE", "EXPERIENCE"),                       # split by the PDF
    ("TECHNIC AL SKIL LS", "TECHNICAL SKILLS"),
    ("CONTAC T", "CONTACT"),
    ("—————Career Timeline                      —————", "Career Timeline"),
    ("Sales Skills", "Sales Skills"),
    ("$ cat skills.yaml", "Skills"),                     # a terminal-style resume
])
def test_headers(line, header):
    """Section headers, however the PDF spaced them."""
    assert header_name(line) == header


@pytest.mark.parametrize("line", [
    "Education Coordinator",            # a job title
    "Languages: Go, Python",            # a skills line
    "Executive presentations",          # a skill, not Title Case
    "Fieldnote Software",
    "languages:",
    "Lean Six Sigma Master Black Belt",
])
def test_not_headers(line):
    """Lines with a header word that aren't headers."""
    assert header_name(line) is None


def test_clean_line_fixes_ligature_gaps_and_icon_glyphs():
    """pypdf layout-mode quirks are undone."""
    assert clean_line("Graduate Certiﬁc              ate, Instructional Design") == (
        "Graduate Certificate, Instructional Design")
    assert clean_line("held 6 oﬃ  ce hours; GAAP ﬁ nancial statements") == (
        "held 6 office hours; GAAP financial statements")
    assert clean_line("trained ﬁve staﬀ auditors") == "trained five staff auditors"
    assert clean_line("Data Scientist II  Northpeak") == "Data Scientist II   Northpeak"
    assert clean_line("Page 2 of 2") == ""


def _sections(lines):
    return sections_from_chunks(page_chunks(lines))


def test_a_sidebar_is_read_as_its_own_column():
    """Headers on both sides of a gutter: each column is read on its own."""
    left = ["C O N T A C T", "(512) 555-0187", "S K I L L S", "User Research", "Prototyping"]
    right = ["Experience", "Senior Product Designer      Mar 2023 – Present",
             "Ledgerline · Austin, TX", "   Lead designer for the invoicing product",
             "   Created the company design system"]
    lines = [f"{l:<40}{r}" for l, r in zip(left, right)]
    sections = _sections(["Priya Raman"] + lines)
    assert sections["Experience"][0].startswith("Senior Product Designer")
    assert sections["CONTACT"] == ["(512) 555-0187"]
    assert sections["SKILLS"] == ["User Research", "Prototyping"]


def test_a_label_column_puts_each_header_on_its_own_line():
    """Headers only on the left: each goes before the text beside it."""
    lines = [
        "EXPERIENCE        Senior Mechanical Engineer              Aug 2022 – Present",
        "                  Voltaris Motors, Auburn Hills, MI",
        "                     Lead engineer for the cold-plate system",
        "EDUCATION         M.S., Mechanical Engineering — University of Michigan     2020",
        "SKILLS            CATIA V5, SolidWorks, NX",
    ]
    sections = _sections(lines)
    assert sections["EXPERIENCE"][0].startswith("Senior Mechanical Engineer")
    assert sections["EDUCATION"][0].startswith("M.S., Mechanical Engineering")
    assert sections["SKILLS"] == ["CATIA V5, SolidWorks, NX"]


def test_a_date_column_stays_beside_its_text():
    """A left-hand date column isn't split off its entries."""
    lines = [
        "Research Experience",
        "2021–present       Graduate Researcher, Achterberg Lab, UC Berkeley",
        "                   Developed a live-cell optogenetic system",
        "2019–2021          Master's Researcher, Swammerdam Institute, Amsterdam",
        "                   Built a single-molecule assay",
    ]
    sections = _sections(lines)
    assert sections["Research Experience"][0].startswith("2021–present       Graduate")
