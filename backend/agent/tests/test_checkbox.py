"""Ticking Greenhouse's checkbox questions, on a local page shaped like the Cloudflare form."""
import pytest

from agent.forms.form_field import FormField
from agent.tests.helpers import bare_form, open_page

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
    """Return a browser page showing the checkbox form."""
    yield from open_page(PAGE)


def _picked(page, key):
    """Return the option ids the page's script saw picked for one question."""
    return page.evaluate("key => picked[key] || []", key)


def test_ticks_only_the_chosen_box_and_the_page_sees_it(page):
    """Only the chosen box is ticked, and the page's own script sees it."""
    form = bare_form()
    form.fill(page, TERMS_FIELD, "Summer (May - September 2027)")
    form.fill(page, ACK_FIELD, "Acknowledge/Confirm")
    assert page.locator(f'[id="{TERMS}_754011949"]').is_checked()
    assert not page.locator(f'[id="{TERMS}_754011948"]').is_checked()
    assert page.locator(f'[id="{ACK}_754011883"]').is_checked()
    assert _picked(page, TERMS) == ["754011949"]
    assert _picked(page, ACK) == ["754011883"]


def test_boxes_stay_ticked_after_later_fields_are_filled(page):
    """Filling later fields doesn't untick the boxes."""
    form = bare_form()
    form.fill(page, TERMS_FIELD, "Summer (May - September 2027)")
    form.fill(page, FormField("first_name", "First Name", "text"), "Test")
    form.fill(page, ACK_FIELD, "Acknowledge/Confirm")
    assert page.locator(f'[id="{TERMS}_754011949"]').is_checked()
    assert page.locator(f'[id="{ACK}_754011883"]').is_checked()


# A pick-several question drawn as a dropdown: the options only exist while it is open
DROPDOWN_PAGE = """
<input id="4033069002" type="text" readonly>
<div id="menu"></div>
<script>
  const box = document.getElementById("4033069002");
  box.addEventListener("click", () => {
    for (const label of ["South Asian", "I don't wish to answer"]) {
      const option = document.createElement("div");
      option.setAttribute("role", "option");
      option.textContent = label;
      option.addEventListener("click", () => { box.value = label; menu.replaceChildren(); });
      menu.append(option);
    }
  });
</script>
"""


def test_picks_from_a_dropdown_when_the_question_has_no_checkboxes(page):
    """The API calls Discord's race question pick-several, but the page shows a dropdown."""
    page.set_content(DROPDOWN_PAGE)
    field = FormField("4033069002", "Race or Ethnicity (optional)", "multi_select",
                      options=["South Asian", "I don't wish to answer"])
    bare_form().fill(page, field, "I don't wish to answer")
    assert page.locator('[id="4033069002"]').input_value() == "I don't wish to answer"
