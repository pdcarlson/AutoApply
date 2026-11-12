"""Ticking Greenhouse's checkbox questions, on a local page shaped like the Cloudflare form."""
import pytest
from playwright.sync_api import sync_playwright

from agent.forms.form_field import FormField
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink

TERMS = "question_69554629[]"
ACK = "question_69554602[]"


def _group(key, label, options):
    """One checkbox question, copying the real fieldset: the name ends in [] and each box's
    id is the name plus the option's value, with a <label for> after a decorative svg."""
    boxes = "".join(f"""
      <div class="checkbox__wrapper"><div class="checkbox__input">
        <input type="checkbox" required id="{key}_{value}" name="{key}" value="{value}">
        <svg class="svg-icon" height="16" width="16" style="position:absolute"></svg>
      </div><label for="{key}_{value}">{text}</label></div>""" for value, text in options)
    return f"""<fieldset class="checkbox" id="{key}" aria-required="true">
      <legend class="label checkbox__description">{label}</legend>{boxes}</fieldset>"""


# Like React's onChange, the page keeps its own list of picks and redraws the boxes from it
# after every change, so a box only stays ticked if the page itself saw it ticked.
PAGE = f"""
<form id="application-form">
  {_group(TERMS, "Which term(s) are you available to intern?",
          [(754011948, "Winter/Spring (January - May 2027)"),
           (754011949, "Summer (May - September 2027)")])}
  <input id="first_name">
  {_group(ACK, "Please review and acknowledge Cloudflare's Candidate Privacy Policy",
          [(754011883, "Acknowledge/Confirm")])}
</form>
<script>
  const picked = {{}};
  document.addEventListener("change", (event) => {{
    const box = event.target;
    if (box.type !== "checkbox") return;
    const list = picked[box.name] = picked[box.name] || [];
    if (box.checked) list.push(box.value); else list.splice(list.indexOf(box.value), 1);
    for (const each of document.querySelectorAll('input[type=checkbox]')) {{
      each.checked = (picked[each.name] || []).includes(each.value);
    }}
  }});
</script>
"""

TERMS_FIELD = FormField(TERMS, "Which term(s) are you available to intern?", "multi_select", True,
                        options=["Winter/Spring (January - May 2027)",
                                 "Summer (May - September 2027)"])
ACK_FIELD = FormField(ACK, "Please review and acknowledge Cloudflare's Candidate Privacy Policy",
                      "multi_select", True, options=["Acknowledge/Confirm"])


@pytest.fixture(name="page")
def fixture_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(PAGE)
        yield page
        browser.close()


def _form():
    return GreenhouseForm(JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/1"))


def _picked(page, key):
    return page.evaluate("key => picked[key] || []", key)


def test_ticks_only_the_chosen_box_and_the_page_sees_it(page):
    form = _form()
    form.fill(page, TERMS_FIELD, "Summer (May - September 2027)")
    form.fill(page, ACK_FIELD, "Acknowledge/Confirm")
    assert page.locator(f'[id="{TERMS}_754011949"]').is_checked()
    assert not page.locator(f'[id="{TERMS}_754011948"]').is_checked()
    assert page.locator(f'[id="{ACK}_754011883"]').is_checked()
    assert _picked(page, TERMS) == ["754011949"]
    assert _picked(page, ACK) == ["754011883"]


def test_boxes_stay_ticked_after_later_fields_are_filled(page):
    form = _form()
    form.fill(page, TERMS_FIELD, "Summer (May - September 2027)")
    form.fill(page, FormField("first_name", "First Name", "text"), "Test")
    form.fill(page, ACK_FIELD, "Acknowledge/Confirm")
    assert page.locator(f'[id="{TERMS}_754011949"]').is_checked()
    assert page.locator(f'[id="{ACK}_754011883"]').is_checked()
