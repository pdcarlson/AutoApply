"""Picking a city suggestion in Greenhouse's location box, on a local page that mimics it."""
import pytest
from playwright.sync_api import Error as PlaywrightError

from agent.forms.form_field import FormField
from agent.tests.helpers import bare_form, open_page

# What Greenhouse really suggested for "Mechanicville" on the Cloudflare form
SUGGESTIONS = ["City of Mechanicville, New York, United States",
               "Mechanicville, New York, United States",
               "Mechanicville, Louisiana, United States"]

PAGE = """
<input id="candidate-location" autocomplete="off">
<div id="menu" role="listbox"></div>
<p id="picked"></p>
<script>
  const box = document.getElementById("candidate-location");
  const menu = document.getElementById("menu");
  box.addEventListener("input", () => {
    menu.innerHTML = "";
    if (box.value.length < 3) return;
    for (const text of %s) {
      const option = document.createElement("div");
      option.setAttribute("role", "option");
      option.textContent = text;
      option.addEventListener("click", () => {
        box.value = text;
        document.getElementById("picked").textContent = text;
        menu.innerHTML = "";
      });
      menu.appendChild(option);
    }
  });
</script>
""" % SUGGESTIONS

LOCATION = FormField("candidate-location", "Location (City)", "location", True,
                     profile_key="location")


@pytest.fixture(name="page")
def fixture_page():
    """Return a browser page showing the location box."""
    yield from open_page(PAGE)


@pytest.mark.parametrize("value", ["Mechanicville, NY", "Mechanicville, New York",
                                   "mechanicville, ny"])
def test_picks_the_city_in_the_right_state(page, value):
    """The city is picked in the state given, however the state is written."""
    bare_form().fill(page, LOCATION, value)
    assert page.locator("#picked").inner_text() == "Mechanicville, New York, United States"


def test_other_state_by_abbreviation(page):
    """A state's abbreviation finds that state's city."""
    bare_form().fill(page, LOCATION, "Mechanicville, LA")
    assert page.locator("#picked").inner_text() == "Mechanicville, Louisiana, United States"


def test_never_picks_a_same_named_city_in_another_state(page):
    """With no city in the right state, filling fails instead of picking another."""
    with pytest.raises(PlaywrightError, match="No location suggestion matches"):
        bare_form().fill(page, LOCATION, "Mechanicville, TX")
    assert page.locator("#picked").inner_text() == ""
