"""Resume sections -> profile fields, on dicts and on real PDFs."""
from pathlib import Path

import pytest

from server import autoapply_modules
from server.resume.dates import read_dates
from server.resume.layout import split_line
from server.resume.mapper import sections_to_profile
from server.tests.job_helpers import EXAMPLE_PDF

FIXTURES = Path(__file__).parent / "fixtures"

# What resumeRead returns for backend/test_fixtures/example_resume.pdf.
EXAMPLE_OTHER = [
    "Jordan Rivera",
    "jordan.rivera@example.com | (555) 010-4477 | Poughkeepsie, NY",
    "Hudson Valley Institute of Technology - B.S. Computer Science, May 2027, GPA 3.6",
    "Riverbend Logistics - Software Engineering Intern, June 2026 to August 2026",
    "ShelfSpace - textbook lending web app (React, TypeScript, Node.js, PostgreSQL)",
    "TrailCount - Raspberry Pi trail counter (Python, SQLite, Flask)",
    "Made-up resume for tests. Not a real person.",
]


@pytest.fixture(name="header_resume_pdf", scope="module")
def fixture_header_resume_pdf(tmp_path_factory):
    """sample_resume_headers.html rendered to PDF with Playwright's Chromium."""
    from playwright.sync_api import sync_playwright  # pylint: disable=import-outside-toplevel  # only this test needs it
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
    """The example resume's opening lines fill the whole profile."""
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
    """Headed sections fill education, experience, projects and skills."""
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


def test_leadership_and_volunteer_sections_become_tagged_experience():
    """Leadership and volunteer sections become tagged experience."""
    sections = {
        "WORK EXPERIENCE": ["Acme Corp                                  June 2024 - Aug 2024",
                            "Intern                                     Boston, MA",
                            "- Built things"],
        "LEADERSHIP EXPERIENCE": [
            "Example Fraternity                         December 2024 - December 2025",
            "President",
            "- Led a 50+ member organization with a $300K budget",
        ],
        "Volunteer Work": ["Food Bank - Volunteer          Jan 2023 - May 2023"],
        "Activities": ["Chess Club", "Robotics Club"],  # no dates: not roles
    }
    patch, unplaced, _ = sections_to_profile(sections)
    assert [(e["kind"], e["org"], e["title"]) for e in patch["experience"]] == [
        ("work", "Acme Corp", "Intern"),
        ("leadership", "Example Fraternity", "President"),
        ("volunteer", "Food Bank", "Volunteer"),
    ]
    leader = patch["experience"][1]
    assert (leader["start"], leader["end"]) == ("2024-12-01", "2025-12-01")
    assert leader["detail"] == "Led a 50+ member organization with a $300K budget"
    assert [u["text"] for u in unplaced] == ["Activities: Chess Club; Robotics Club"]


def test_two_degrees_under_one_school_are_two_entries():
    """Two degrees under one school are two entries."""
    sections = {"EDUCATION": [
        "Example Polytechnic Institute                                        Troy, NY",
        "Master of Science in Computer Science, GPA 4.0          "
        "January 2026 - Expected December 2026",
        "Bachelor of Science in Computer Science, GPA 3.62          August 2022 - December 2025",
    ]}
    patch, unplaced, _ = sections_to_profile(sections)
    pick = ("id", "school", "location", "degreeType", "major", "gpa", "start", "end")
    assert [{k: e[k] for k in pick} for e in patch["education"]] == [
        {"id": "ed-1", "school": "Example Polytechnic Institute", "location": "Troy, NY",
         "degreeType": "Master of Science", "major": "Computer Science", "gpa": "4.0",
         "start": "2026-01-01", "end": "2026-12-01"},
        {"id": "ed-2", "school": "Example Polytechnic Institute", "location": "Troy, NY",
         "degreeType": "Bachelor of Science", "major": "Computer Science", "gpa": "3.62",
         "start": "2022-08-01", "end": "2025-12-01"},
    ]
    assert unplaced == []


GAP = " " * 40  # the space pypdf leaves before a right-aligned date or place

# The lines a PDF gives for a resume whose long bullets wrap onto a second line
WRAPPED = {
    "EDUCATION": [
        f"Northeastern University{GAP}Boston, MA",
        f"Bachelor of Science in Computer Science | GPA: 3.65/4.00{GAP}Expected May 2028",
        "Relevant Coursework: Data Structures & Algorithms, Database Systems, Computer Networks,",
        "Operating Systems, Software Engineering",
    ],
    "EXPERIENCE": [
        f"HarborTech Solutions{GAP}Boston, MA",
        f"Software Engineering Intern{GAP}May 2026 – Aug 2026",
        "•  Built REST API endpoints using Python, Flask, and PostgreSQL for an internal analytics",
        "dashboard used by 20+ employees.",
        "•  Developed reusable React components for filtering and exporting reports, reducing the",
        "operations team's manual steps.",
    ],
    "PROJECTS": [
        f"Campus Event Finder | React, Node.js, Express, PostgreSQL{GAP}Jan 2026 – Apr 2026",
        "•  Developed a full-stack web app allowing students to find campus events, and bookmark",
        "events.",
        "•  Designed REST endpoints and a database schema for saved events; added",
        "input validation and basic authentication.",
        "•  Deployed the application and documented local setup in GitHub.",
        f"Personal Budget Tracker | Python, Flask, SQLite, Chart.js{GAP}Sep 2025 – Dec 2025",
        "•  Created a budget tracking application to visualize spending trends by",
        "month.",
    ],
    "LEADERSHIP & ACTIVITIES": [
        f"Computer Science Club | Member{GAP}Sep 2024 – Present",
        "•  Participate in weekly technical workshops and student hackathons.",
        f"Peer Tutor, Intro to Programming | Northeastern University{GAP}Sep 2025 – Present",
        "•  Help students debug Python and Java assignments during weekly tutoring",
        "hours.",
    ],
}


def test_wrapped_bullet_lines_stay_with_their_entry():
    """A bullet's wrapped second line ("events.") is part of that bullet, not a new entry."""
    patch, unplaced, _ = sections_to_profile(WRAPPED)
    assert [p["name"] for p in patch["projects"]] == ["Campus Event Finder",
                                                     "Personal Budget Tracker"]
    assert patch["projects"][0]["detail"].split("\n") == [
        "Developed a full-stack web app allowing students to find campus events, and "
        "bookmark events.",
        "Designed REST endpoints and a database schema for saved events; added input validation "
        "and basic authentication.",
        "Deployed the application and documented local setup in GitHub.",
    ]
    assert patch["projects"][1]["detail"] == ("Created a budget tracking application to visualize "
                                              "spending trends by month.")
    assert [(e["kind"], e["org"], e["title"]) for e in patch["experience"]] == [
        ("work", "HarborTech Solutions", "Software Engineering Intern"),
        ("leadership", "Computer Science Club", "Member"),
        ("leadership", "Northeastern University", "Peer Tutor, Intro to Programming"),
    ]
    assert patch["experience"][0]["detail"].split("\n") == [
        "Built REST API endpoints using Python, Flask, and PostgreSQL for an internal analytics "
        "dashboard used by 20+ employees.",
        "Developed reusable React components for filtering and exporting reports, reducing the "
        "operations team's manual steps.",
    ]
    assert patch["education"][0]["coursework"].endswith("Operating Systems, Software Engineering")
    assert unplaced == []


@pytest.mark.parametrize("lines, count", [
    # A new role after a finished bullet, with its dates on the next line
    (["Acme Corp", "Intern     June 2024 - Aug 2024", "- Built things.",
      "Globex Inc", "Analyst     June 2023 - Aug 2023", "- Ran reports."], 2),
    # A new role after a bullet with no period, named in one capitalized line
    (["Acme Corp     June 2024 - Aug 2024", "- Built things",
      "iOS Developer at Initech     June 2023 - Aug 2023", "- Shipped an app"], 2),
])
def test_a_new_entry_after_a_bullet_is_not_joined_to_it(lines, count):
    """Joining wrapped lines never swallows the next role's head line."""
    patch, _, _ = sections_to_profile({"EXPERIENCE": lines})
    assert len(patch["experience"]) == count


@pytest.mark.parametrize("text, dates", [
    ("2019 – Present", ("2019-01-01", "", True)),
    ("2021–present", ("2021-01-01", "", True)),
    ("Apr 2023  Present", ("2023-04-01", "", True)),        # the dash glyph was lost
    ("Dates: 03/2021 – 06/2022", ("2021-03-01", "2022-06-01", False)),
    ("2023-03 .. present", ("2023-03-01", "", True)),
    ("Sep. 2021 – May 2026", ("2021-09-01", "2026-05-01", False)),
    ("Spring 2024", ("", "2024-01-01", False)),
    ("Expected Dec 2027", ("", "2027-12-01", False)),
])
def test_date_forms(text, dates):
    """Year-only, numeric, season and dash-less dates."""
    found = read_dates(text)
    assert (found.start, found.end, found.current) == dates


def test_roles_without_bullet_characters():
    """PDFs often drop bullet glyphs: roles come from dates, short head lines and indents."""
    sections = {"EXPERIENCE": [
        # title then organization, the bullets wrapped and unmarked
        "Software Engineer I                                        Jun. 2026 – Present",
        "Halcyon Logistics                                                   Boston, MA",
        "Build and maintain shipment-tracking microservices in Go and gRPC, handling 40M+",
        "status events per day",
        "Cut p95 latency of the route-quote API from 820ms to 210ms with a Redis cache",
        # dates on the second line, under "Title  Org"
        "Data Scientist  Ripple Fitness",
        "Portland, OR · Jul 2021  Mar 2023",
        "  Forecast class demand across 60 studios",
        # a left-hand timeline: start date, then end date on the next line
        "        Jun 2017        Digital Marketing Specialist",
        "        Dec 2019       Monarch & Finch Agency · Milwaukee, WI",
        "                           Planned paid search campaigns for 10 retail clients",
    ]}
    patch, _, _ = sections_to_profile(sections)
    roles = [(e["title"], e["org"], e["location"], e["start"], e["end"], e["current"])
             for e in patch["experience"]]
    assert roles == [
        ("Software Engineer I", "Halcyon Logistics", "Boston, MA", "2026-06-01", "", True),
        ("Data Scientist", "Ripple Fitness", "Portland, OR", "2021-07-01", "2023-03-01", False),
        ("Digital Marketing Specialist", "Monarch & Finch Agency", "Milwaukee, WI",
         "2017-06-01", "2019-12-01", False),
    ]
    assert patch["experience"][0]["detail"].split("\n") == [
        "Build and maintain shipment-tracking microservices in Go and gRPC, handling 40M+ "
        "status events per day",
        "Cut p95 latency of the route-quote API from 820ms to 210ms with a Redis cache",
    ]


def test_federal_style_roles_with_labels():
    """"Title:" and "Dates:" lines; the employer is the line above the dates."""
    sections = {"WORK EXPERIENCE": [
        "U.S. Department of Transportation, Federal Transit Administration",
        "1200 New Jersey Avenue SE, Washington, DC 20590",
        "Dates: 03/2021 – Present  |  Hours per week: 40",
        "Title: Management and Program Analyst",
        "    PROGRAM EVALUATION: Lead evaluations of competitive grant programs.",
        "U.S. Department of Veterans Affairs, Veterans Benefits Administration",
        "810 Vermont Avenue NW, Washington, DC 20420",
        "Dates: 07/2018 – 03/2021  |  Hours per week: 40",
        "Title: Program Analyst (converted to permanent 07/2019)",
        "    DATA ANALYSIS: Analyzed claims-processing data for 56 regional offices.",
    ]}
    patch, _, _ = sections_to_profile(sections)
    assert [(e["title"], e["org"], e["location"], e["start"], e["end"])
            for e in patch["experience"]] == [
        ("Management and Program Analyst",
         "U.S. Department of Transportation, Federal Transit Administration",
         "Washington, DC", "2021-03-01", ""),
        ("Program Analyst", "U.S. Department of Veterans Affairs, Veterans Benefits Administration",
         "Washington, DC", "2018-07-01", "2021-03-01"),
    ]


def test_education_school_on_its_own_line_and_year_dates():
    """The school is the line naming one; "M.Arch — ETH Zürich" has no major."""
    sections = {"EDUCATION": [
        "M.S., Statistics", "University of Washington", "2019  2021 · GPA 3.9",
        "B.A., Mathematics & Economics", "Pomona College", "2015  2019",
        "M.Arch — ETH Zürich                                      2014–2016",
    ]}
    patch, unplaced, _ = sections_to_profile(sections)
    pick = ("school", "degreeType", "major", "gpa", "start", "end")
    assert [tuple(e[k] for k in pick) for e in patch["education"]] == [
        ("University of Washington", "M.S.", "Statistics", "3.9", "2019-01-01", "2021-01-01"),
        ("Pomona College", "B.A.", "Mathematics & Economics", "", "2015-01-01", "2019-01-01"),
        ("ETH Zürich", "M.Arch", "", "", "2014-01-01", "2016-01-01"),
    ]
    assert unplaced == []


def test_contact_quirks():
    """Credentials after a name, a two-space phone, an icon glyph glued to a URL."""
    sections = {"Other": [
        "Anthony DiMarco, P.E.                                 Atlanta, GA",
        "✉sofia@example.com        ☎ 206  555 0124        inlinkedin.com/in/someone",
    ]}
    patch, _, _ = sections_to_profile(sections)
    assert (patch["firstName"], patch["lastName"]) == ("Anthony", "DiMarco")
    assert (patch["city"], patch["state"], patch["phone"]) == ("Atlanta", "GA", "206 555 0124")
    assert patch["links"][1]["url"] == "https://linkedin.com/in/someone"


def test_split_line_takes_a_right_hand_date_column():
    """A right-hand date column and place column are split off."""
    assert split_line("Acme - Intern      Boston, MA      June 2024 - Aug 2024") == (
        "Acme - Intern", "June 2024 - Aug 2024", "Boston, MA")


def test_example_resume_pdf_parses():
    """The example resume PDF reads into the expected lines."""
    sections = autoapply_modules.read_resume(EXAMPLE_PDF)
    assert sections["Other"] == EXAMPLE_OTHER
    assert autoapply_modules.page_count(EXAMPLE_PDF) == 1


def test_header_fixture_pdf_parses_with_case_insensitive_headers(header_resume_pdf):
    """A rendered PDF with upper-case headers parses into the profile."""
    sections = autoapply_modules.read_resume(header_resume_pdf)
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
    """A PDF with no text reads as None."""
    from pypdf import PdfWriter  # pylint: disable=import-outside-toplevel  # only this test needs it
    blank = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(blank, "wb") as handle:
        writer.write(handle)
    assert autoapply_modules.read_resume(blank) is None
