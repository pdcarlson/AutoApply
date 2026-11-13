"""The agent opens the job link exactly as pasted, and falls back to Greenhouse's embed page."""
from playwright.sync_api import sync_playwright

from agent.forms import greenhouse_form
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink

PASTED = "https://job-boards.greenhouse.io/singlestore/jobs/8205389?jr_id=6aa9bc6d28e24cb38513bc94"


def test_keeps_the_pasted_link_but_still_means_the_same_job():
    link = JobLink.parse(PASTED)
    assert link.pasted == PASTED
    assert link.url == "https://job-boards.greenhouse.io/singlestore/jobs/8205389"
    assert link == JobLink.parse("https://boards.greenhouse.io/singlestore/jobs/8205389")


def test_opens_the_pasted_link_unchanged():
    assert GreenhouseForm(JobLink.parse(PASTED)).form_url() == PASTED


def test_falls_back_to_embed_page_when_the_form_isnt_there(tmp_path, monkeypatch):
    """A link that lands on a careers page without the form switches to the embed page."""
    careers = tmp_path / "careers.html"
    careers.write_text("<p>Our careers site, with the form in a frame</p>", encoding="utf-8")
    embed = tmp_path / "embed.html"
    embed.write_text('<form id="application-form"></form>', encoding="utf-8")
    monkeypatch.setattr(greenhouse_form, "FORM_WAIT_MS", 500)

    form = GreenhouseForm(JobLink.parse(PASTED))
    monkeypatch.setattr(form, "embed_url", embed.as_uri)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(careers.as_uri())
        form.wait_until_ready(page)
        assert page.url == embed.as_uri()
        browser.close()
