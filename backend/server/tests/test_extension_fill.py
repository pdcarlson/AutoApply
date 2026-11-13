"""The extension's fill script (extension/fill.js) on the fake Lever page, with the plan the
server gives it: what the person's own browser ends up showing. Never presses Submit.
"""
# pylint: disable=redefined-outer-name,unused-argument
import base64
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from server.tests.job_helpers import EXAMPLE_PDF, FAKE_LEVER_URL, add_job, set_up_profile

EXTENSION = Path(__file__).resolve().parents[3] / "extension"
FAKE_PAGE = Path(__file__).resolve().parents[2] / "agent" / "tests" / "fake_forms" / "lever_form.html"
SCHOOL = "Which school do you attend?"
WHY_HERE = "Why do you want to work here?"

FILL = """async ([plan, resume]) => {
  const bytes = Uint8Array.from(atob(resume), (character) => character.charCodeAt(0));
  const file = new File([bytes], plan.resume.name, { type: "application/pdf" });
  return AutoApplyFill.fillLever(plan, file);
}"""


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr("agent.forms.lever_form.urlopen", refuse)


@pytest.fixture
def plan(client, app):
    """The server's fill plan for the fake Lever job, with every question answered."""
    set_up_profile(client)
    add_job(client, FAKE_LEVER_URL)
    bank = app.state.answer_bank
    bank.upsert_by_question(SCHOOL, "Rensselaer Polytechnic Institute", origin="manual",
                            source="Test")
    bank.upsert_by_question(WHY_HERE, "I like building tools people use.", origin="manual",
                            source="Test")
    return client.get("/api/extension/plan", params={"url": FAKE_LEVER_URL}).json()


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        yield page
        browser.close()


def open_form(page, query=""):
    page.goto(FAKE_PAGE.resolve().as_uri() + query)
    page.add_script_tag(path=str(EXTENSION / "fill.js"))


def test_fill_script_fills_the_form_from_the_plan(plan, page):
    open_form(page, "?banner=1")  # a cookie banner over the page must not matter
    resume = base64.b64encode(EXAMPLE_PDF.read_bytes()).decode()
    result = page.evaluate(FILL, [plan, resume])

    assert result["missed"] == []
    assert result["filled"][0] == "Resume/CV" and len(result["filled"]) == len(plan["fields"]) + 1
    assert page.locator('[name="name"]').input_value() == "Jordan Rivera"
    assert page.locator('[name="email"]').input_value() == "jordan.rivera@example.com"
    assert page.locator("#location-input").input_value() == "Poughkeepsie, NY, USA"
    assert "Poughkeepsie, NY, USA" in page.locator("#selected-location").input_value()
    assert page.locator('[name="cards[abc][field0]"][value="Yes"]').is_checked()
    assert page.locator('[name="cards[abc][field1]"]').evaluate(
        "select => select.selectedOptions[0].text") == "Rensselaer Polytechnic Institute"
    assert page.locator('[name="cards[abc][field3]"]').input_value() \
        == "I like building tools people use."
    assert page.locator("#resume-upload-input").evaluate(
        "input => [input.files.length, input.files[0].name, input.files[0].size]") \
        == [1, "example_resume.pdf", EXAMPLE_PDF.stat().st_size]
    assert page.locator(".resume-upload-success").is_visible()
    assert page.locator("#application-form").count() == 1  # filled, not submitted
    assert page.locator('[name="eeo[gender]"]').input_value() == ""  # left alone


def test_fill_script_reports_what_it_could_not_fill(plan, page):
    """An answer that isn't one of the form's choices is reported, and nothing wrong is picked."""
    for form_field in plan["fields"]:
        if form_field["label"] == SCHOOL:
            form_field["value"] = "A School That Isn't Listed"
    plan["fields"].append({"key": "not-on-the-page", "label": "Gone", "kind": "text",
                           "value": "x"})
    open_form(page)
    result = page.evaluate(FILL, [plan, base64.b64encode(EXAMPLE_PDF.read_bytes()).decode()])
    assert result["missed"] == [SCHOOL, "Gone"]
    assert page.locator('[name="cards[abc][field1]"]').input_value() == ""
