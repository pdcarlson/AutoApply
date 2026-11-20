"""The resume reader splits a resume into sections at its headers."""
from pathlib import Path

from onboarding.resume_sections import is_header, page_count, read_resume, sections_from_lines

EXAMPLE_PDF = Path(__file__).resolve().parents[2] / "test_fixtures" / "example_resume.pdf"


def test_headers_match_in_any_case():
    """Headers match in any case and with trailing punctuation, but long lines never do."""
    assert is_header("EDUCATION")
    assert is_header("Skills:")
    assert not is_header("Hudson Valley Institute of Technology")


def test_sections_from_lines():
    """Lines before the first header go under "Other", and blank lines are dropped."""
    assert sections_from_lines(["Jo", "", "SKILLS", "Python"]) == {
        "Other": ["Jo"], "SKILLS": ["Python"]}


def test_missing_and_unsupported_files_read_as_none(tmp_path):
    """A missing file and a non-resume file both read as None."""
    assert read_resume(tmp_path / "nope.pdf") is None
    text_file = tmp_path / "resume.txt"
    text_file.write_text("Education", encoding="utf-8")
    assert read_resume(text_file) is None
    assert page_count(text_file) is None


def test_example_resume_reads_into_lines():
    """The example resume reads into sections of text lines."""
    resume = read_resume(EXAMPLE_PDF)
    assert resume is not None and resume["Other"]
    assert all(isinstance(line, str) for lines in resume.values() for line in lines)
    assert page_count(EXAMPLE_PDF) == 1
