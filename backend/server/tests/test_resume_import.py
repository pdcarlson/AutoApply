"""resumeRead sections -> profile (spec 2.12), on dicts and on real PDFs."""
# pylint: disable=redefined-outer-name,unused-argument  # pytest fixtures
from pathlib import Path

import pytest

from server import konefal
from server.resume_import import sections_to_profile, split_line

FIXTURES = Path(__file__).parent / "fixtures"

# What resumeRead returns for backend/agent/applicant/example_resume.pdf (spec 1.3).
EXAMPLE_OTHER = [
    "Jordan Rivera",
    "jordan.rivera@example.com | (555) 010-4477 | Poughkeepsie, NY",
    "Hudson Valley Institute of Technology - B.S. Computer Science, May 2027, GPA 3.6",
    "Riverbend Logistics - Software Engineering Intern, June 2026 to August 2026",
    "ShelfSpace - textbook lending web app (React, TypeScript, Node.js, PostgreSQL)",
    "TrailCount - Raspberry Pi trail counter (Python, SQLite, Flask)",
    "Made-up resume for tests. Not a real person.",
]


@pytest.fixture(scope="module")
def header_resume_pdf(tmp_path_factory):
    """sample_resume_headers.html rendered to PDF with Playwright's Chromium."""
    from playwright.sync_api import sync_playwright  # pylint: disable=import-outside-toplevel
    out = tmp_path_factory.mktemp("resume") / "sample_resume_headers.pdf"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto((FIXTURES / "sample_resume_headers.html").as_uri())
            page.pdf(path=str(out), format="Letter")
        finally:
            browser.close()
    return out


def test_example_resume_other_section():
    patch, unplaced, labels = sections_to_profile({"Other": EXAMPLE_OTHER})
    assert (patch["firstName"], patch["middleName"], patch["lastName"]) == (
        "Jordan", "", "Rivera")
    assert patch["email"] == "jordan.rivera@example.com"
    assert patch["phone"] == "(555) 010-4477"
    assert (patch["city"], patch["state"]) == ("Poughkeepsie", "NY")

    school = patch["education"][0]
    assert school["id"] == "ed-1"
    assert school["school"] == "Hudson Valley Institute of Technology"
    assert school["degreeType"] == "B.S."
    assert school["major"] == "Computer Science"
    assert school["gpa"] == "3.6"
    assert school["end"] == "2027-05-01"

    job = patch["experience"][0]
    assert (job["id"], job["org"], job["title"]) == ("x-1", "Riverbend Logistics",
                                                     "Software Engineering Intern")
    assert (job["start"], job["end"], job["current"]) == ("2026-06-01", "2026-08-01", False)

    assert [(p["name"], p["tech"]) for p in patch["projects"]] == [
        ("ShelfSpace", "React, TypeScript, Node.js, PostgreSQL"),
        ("TrailCount", "Python, SQLite, Flask"),
    ]
    assert patch["projects"][0]["detail"] == "textbook lending web app"
    # no Skills section: derived from the project tech, deduplicated in order
    assert patch["skills"] == ["React", "TypeScript", "Node.js", "PostgreSQL", "Python",
                               "SQLite", "Flask"]

    assert unplaced == [{"id": "un-1", "text": "Made-up resume for tests. Not a real person.",
                         "suggestion": None}]
    assert labels == [
        {"status": "ok", "label": "Contact info · 4 fields"},
        {"status": "ok", "label": "Education · Hudson Valley Institute of Technology"},
        {"status": "ok", "label": "Experience · 1 role"},
        {"status": "ok", "label": "Projects · 2"},
        {"status": "warn", "label": "Skills · 7"},
        {"status": "warn", "label": "1 section we couldn’t place"},
    ]


def test_header_sections_on_dicts():
    sections = {
        "Other": ["SAM LEE", "sam@example.com   linkedin.com/in/samlee   Boston, MA"],
        "Experience": [
            "Teaching Assistant, Example University        Jan 2025 – Present",
            "• Held office hours",
            "• Graded labs",
            "Acme Corp - Intern        June 2024 - Aug 2024",
        ],
        "Technical Skills:": ["Languages: Python, Go; Tools: Git | Docker"],
        "Awards": ["Dean's List", "Hackathon winner"],
        "Projects": ["Planner | React, TypeScript", "- Plans courses"],
    }
    patch, unplaced, labels = sections_to_profile(sections)
    assert (patch["firstName"], patch["middleName"], patch["lastName"]) == ("Sam", "", "Lee")
    assert patch["links"][1]["url"] == "https://linkedin.com/in/samlee"
    assert (patch["city"], patch["state"]) == ("Boston", "MA")
    first, second = patch["experience"]
    assert (first["title"], first["org"], first["current"], first["end"]) == (
        "Teaching Assistant", "Example University", True, "")
    assert first["start"] == "2025-01-01" and first["detail"] == "Held office hours\nGraded labs"
    assert (second["org"], second["title"], second["end"]) == ("Acme Corp", "Intern", "2024-08-01")
    assert patch["skills"] == ["Python", "Go", "Git", "Docker"]
    assert patch["projects"] == [{"id": "p-1", "name": "Planner", "tech": "React, TypeScript",
                                  "detail": "Plans courses"}]
    assert unplaced == [{"id": "un-1", "text": "Awards: Dean's List; Hackathon winner",
                         "suggestion": "Add as a custom field"}]
    assert {"status": "ok", "label": "Skills · 4"} in labels


def test_split_line_takes_a_right_hand_date_column():
    assert split_line("Acme - Intern      Boston, MA      June 2024 - Aug 2024") == (
        "Acme - Intern", "June 2024 - Aug 2024", "Boston, MA")


def test_example_resume_pdf_parses():
    pdf = Path(__file__).resolve().parents[2] / "agent" / "applicant" / "example_resume.pdf"
    sections = konefal.read_resume(pdf)
    assert sections["Other"] == EXAMPLE_OTHER
    assert konefal.page_count(pdf) == 1


def test_header_fixture_pdf_parses_with_case_insensitive_headers(header_resume_pdf):
    sections = konefal.read_resume(header_resume_pdf)
    assert {"EDUCATION", "RELEVANT COURSEWORK", "EXPERIENCE", "SKILLS"} <= set(sections)

    patch, unplaced, labels = sections_to_profile(sections)
    assert (patch["firstName"], patch["lastName"]) == ("Alex", "Morgan")
    assert patch["links"][2]["url"] == "https://github.com/alexmorgan"
    school = patch["education"][0]
    assert (school["school"], school["major"], school["gpa"]) == (
        "Example State University", "Computer Science", "3.8")
    assert (school["start"], school["end"]) == ("2023-08-01", "2027-05-01")
    job = patch["experience"][0]
    assert (job["org"], job["title"], job["start"], job["end"]) == (
        "Acme Robotics", "Software Intern", "2025-06-01", "2025-08-01")
    assert "telemetry" in job["detail"]
    assert patch["skills"] == ["Python", "Java", "SQL"]
    assert unplaced == [{
        "id": "un-1",
        "text": "Relevant Coursework: Data Structures, Operating Systems, Databases",
        "suggestion": "Add to Education"}]
    assert {"status": "ok", "label": "Skills · 3"} in labels


def test_empty_text_gives_none(tmp_path):
    from pypdf import PdfWriter  # pylint: disable=import-outside-toplevel
    blank = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(blank, "wb") as handle:
        writer.write(handle)
    assert konefal.read_resume(blank) is None
