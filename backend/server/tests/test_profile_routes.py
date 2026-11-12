"""Resume upload and parse, profile and confirm routes (spec 2.12)."""
import io
import time
from pathlib import Path

EXAMPLE_PDF = Path(__file__).resolve().parents[2] / "agent" / "applicant" / "example_resume.pdf"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(client, name, content, mime=PDF, path="/api/resume", method="post"):
    return getattr(client, method)(path, files={"file": (name, content, mime)})


def _wait_for_parse(client, timeout=20.0):
    deadline = time.monotonic() + timeout
    while True:
        parse = client.get("/api/resume/parse").json()
        if parse["status"] != "parsing" or time.monotonic() > deadline:
            return parse
        time.sleep(0.05)


def _upload_example(client):
    response = _upload(client, "example_resume.pdf", EXAMPLE_PDF.read_bytes())
    assert response.status_code == 202, response.text
    return response.json(), _wait_for_parse(client)


def test_parse_is_404_before_any_upload(client):
    response = client.get("/api/resume/parse")
    assert response.status_code == 404 and response.json()["code"] == "not_found"


def test_upload_parses_into_the_profile(client, app):
    started, parse = _upload_example(client)
    assert started["status"] == "parsing" and started["sections"] == []
    assert started["error"] is None
    assert started["file"]["name"] == "example_resume.pdf"
    assert started["file"]["sizeBytes"] == EXAMPLE_PDF.stat().st_size
    assert started["file"]["pageCount"] == 1
    assert set(started) == {"status", "file", "sections", "error"}

    assert parse["status"] == "done", parse
    assert len(parse["sections"]) >= 4
    assert parse["sections"][0] == {"status": "ok", "label": "Contact info · 4 fields"}

    profile = client.get("/api/profile").json()
    assert "_resumePath" not in profile
    assert profile["name"] == "Jordan Rivera" and profile["city"] == "Poughkeepsie"
    assert profile["education"][0]["school"] == "Hudson Valley Institute of Technology"
    assert len(profile["projects"]) == 2 and profile["resume"]["name"] == "example_resume.pdf"
    assert profile["unplaced"][0]["suggestion"] is None

    stored = app.state.store.read("profile")
    assert stored["_resumePath"] == "resume/example_resume.pdf"
    assert app.state.store.path("resume", "example_resume.pdf").read_bytes() == \
        EXAMPLE_PDF.read_bytes()


def test_rejects_wrong_type_and_large_files(client):
    response = _upload(client, "resume.txt", b"hello", mime="text/plain")
    assert response.status_code == 422 and response.json()["code"] == "invalid_type"
    assert "resume.txt" in response.json()["message"]
    response = client.post("/api/resume")
    assert response.status_code == 422 and response.json()["code"] == "invalid_type"
    response = _upload(client, "big.pdf", b"0" * (6 * 1024 * 1024))
    assert response.status_code == 422 and response.json()["code"] == "too_large"
    assert client.get("/api/resume/parse").status_code == 404


def test_unreadable_pdf_fails_with_unreadable(client):
    response = _upload(client, "broken.PDF", b"%PDF-1.4 not really a pdf")
    assert response.status_code == 202
    parse = _wait_for_parse(client)
    assert parse["status"] == "failed"
    assert parse["error"]["code"] == "unreadable"
    assert "broken.PDF" in parse["error"]["message"]


def test_replace_resume_file_keeps_the_profile(client, app):
    _upload_example(client)
    before = client.get("/api/profile").json()
    response = _upload(client, "new resume.pdf", EXAMPLE_PDF.read_bytes(), path="/api/resume/file",
                       method="put")
    assert response.status_code == 200
    resume = response.json()
    assert set(resume) == {"name", "sizeBytes", "pageCount", "uploadedAt"}
    assert resume["name"] == "new resume.pdf"
    after = client.get("/api/profile").json()
    assert after["resume"] == resume
    assert {k: v for k, v in after.items() if k != "resume"} == \
        {k: v for k, v in before.items() if k != "resume"}
    files = sorted(p.name for p in app.state.store.path("resume").iterdir())
    assert files == ["new resume.pdf"]  # the previous file is gone
    bad = _upload(client, "x.png", b"png", mime="image/png", path="/api/resume/file",
                  method="put")
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_type"


def test_put_profile_replaces_editable_fields_only(client):
    _upload_example(client)
    profile = client.get("/api/profile").json()
    update = {k: v for k, v in profile.items() if k not in ("resume", "unplaced")}
    update["name"] = "Jordan R."
    update["custom"] = [{"id": "cf-1", "label": "Pronouns", "value": "they/them"}]
    response = client.put("/api/profile", json=update)
    assert response.status_code == 200
    saved = response.json()
    assert saved["name"] == "Jordan R." and saved["custom"][0]["value"] == "they/them"
    assert saved["resume"] == profile["resume"] and saved["unplaced"] == profile["unplaced"]
    bad = client.put("/api/profile", json={"skills": "not a list"})
    assert bad.status_code == 422


def test_unplaced_accept_and_dismiss(client, app):
    with app.state.store.tx() as db:
        db.profile["education"] = [{"id": "ed-1", "school": "Example State University",
                                    "degreeType": "", "major": "", "gpa": "", "location": "",
                                    "start": "", "end": "", "coursework": ""}]
        db.profile["unplaced"] = [
            {"id": "un-1", "text": "Relevant Coursework: Data Structures, Databases",
             "suggestion": "Add to Education"},
            {"id": "un-2", "text": "Awards: Dean's List", "suggestion": "Add as a custom field"},
            {"id": "un-3", "text": "Made-up resume for tests.", "suggestion": None},
        ]
    profile = client.post("/api/profile/unplaced/un-1", json={"action": "accept"}).json()
    assert profile["education"][0]["coursework"] == "Data Structures, Databases"
    assert [u["id"] for u in profile["unplaced"]] == ["un-2", "un-3"]

    profile = client.post("/api/profile/unplaced/un-2", json={"action": "accept"}).json()
    assert profile["custom"] == [{"id": "cf-1", "label": "Awards", "value": "Dean's List"}]

    profile = client.post("/api/profile/unplaced/un-3", json={"action": "dismiss"}).json()
    assert profile["unplaced"] == [] and len(profile["custom"]) == 1

    missing = client.post("/api/profile/unplaced/un-9", json={"action": "accept"})
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_coursework_without_education_becomes_a_custom_field(client, app):
    with app.state.store.tx() as db:
        db.profile["unplaced"] = [{"id": "un-1", "text": "Relevant Coursework: Compilers",
                                   "suggestion": "Add to Education"}]
    profile = client.post("/api/profile/unplaced/un-1", json={"action": "accept"}).json()
    assert profile["custom"] == [{"id": "cf-1", "label": "Relevant Coursework",
                                  "value": "Compilers"}]


def test_confirm_profile(signed_in):
    response = signed_in.post("/api/profile/confirm")
    assert response.status_code == 200 and response.json()["profileConfirmed"] is True
    assert signed_in.get("/api/session").json()["profileConfirmed"] is True


def test_docx_resume_parses(client):
    import docx  # pylint: disable=import-outside-toplevel
    document = docx.Document()
    document.add_paragraph("Casey Nguyen")
    document.add_paragraph("casey@example.com | (555) 222-3333 | Austin, TX")
    document.add_paragraph("EDUCATION")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Example University - B.A. Mathematics"
    table.rows[0].cells[1].text = "Aug 2022 - May 2026"
    document.add_paragraph("SKILLS")
    document.add_paragraph("Python, R, LaTeX")
    buffer = io.BytesIO()
    document.save(buffer)

    response = _upload(client, "casey.docx", buffer.getvalue(), mime=DOCX)
    assert response.status_code == 202
    assert response.json()["file"]["pageCount"] is None
    parse = _wait_for_parse(client)
    assert parse["status"] == "done", parse
    profile = client.get("/api/profile").json()
    assert profile["name"] == "Casey Nguyen" and profile["state"] == "TX"
    school = profile["education"][0]
    assert (school["school"], school["degreeType"], school["major"]) == (
        "Example University", "B.A.", "Mathematics")
    assert (school["start"], school["end"]) == ("2022-08-01", "2026-05-01")
    assert profile["skills"] == ["Python", "R", "LaTeX"]


def test_delete_account_removes_the_resume(signed_in, app):
    _upload_example(signed_in)
    assert signed_in.delete("/api/account").status_code == 204
    assert not app.state.store.path("resume").exists()
    assert signed_in.get("/api/resume/parse").status_code == 404
    assert signed_in.get("/api/profile").json()["resume"] is None
