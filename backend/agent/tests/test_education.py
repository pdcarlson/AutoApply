"""Filling Greenhouse's Education section, on a local page that mimics it."""
import json

import pytest
from playwright.sync_api import sync_playwright

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.forms.form_field import FieldAnswer
from agent.forms.greenhouse_form import (GreenhouseForm, education_config_from_page,
                                         fields_from_api)
from agent.jobs.job_link import JobLink
from agent.runner.apply_run import ApplyRun

LINK = JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/1")
# Part of what Greenhouse's API really lists
OPTIONS = {"degrees": ["Associate's Degree", "Bachelor's Degree", "Master's Degree",
                       "Master of Business Administration (M.B.A.)", "Other"],
           "disciplines": ["Computer Engineering", "Computer Science",
                           "Computer Science and Engineering", "Other"]}
SCHOOLS = ["Rensselaer Polytechnic Institute", "Rensselaer at Hartford", "Other"]

# The school box searches as you type, showing "Loading..." first, like Greenhouse's.
# This form has no start date boxes, like some real ones.
PAGE = """
<form id="application-form">
  <input id="school--0" autocomplete="off">
  <p id="picked-school"></p>
  <select id="degree--0"><option value="">Select...</option>%(degrees)s</select>
  <select id="discipline--0"><option value="">Select...</option>%(disciplines)s</select>
  <select id="end-month--0"><option value="">Select...</option>
    <option>April</option><option>May</option><option>June</option></select>
  <input id="end-year--0" type="number">
  <div id="menu"></div>
</form>
<script>
  const box = document.getElementById("school--0");
  const menu = document.getElementById("menu");
  let search = 0;
  box.addEventListener("input", () => {
    const mine = ++search;
    menu.innerHTML = '<div class="select__menu"><div class="select__menu-notice--loading">' +
                     'Loading...</div></div>';
    setTimeout(() => {
      if (mine !== search) return;
      const list = document.createElement("div");
      list.className = "select__menu";
      const term = box.value.toLowerCase();
      for (const text of %(schools)s.filter(s => s.toLowerCase().includes(term))) {
        const option = document.createElement("div");
        option.setAttribute("role", "option");
        option.textContent = text;
        option.addEventListener("click", () => {
          document.getElementById("picked-school").textContent = text;
          menu.innerHTML = "";
        });
        list.appendChild(option);
      }
      if (!list.children.length) list.innerHTML = "<div>No options</div>";
      menu.replaceChildren(list);
    }, 300);
  });
</script>
""" % {"degrees": "".join(f"<option>{d}</option>" for d in OPTIONS["degrees"]),
       "disciplines": "".join(f"<option>{d}</option>" for d in OPTIONS["disciplines"]),
       "schools": json.dumps(SCHOOLS)}


def profile(**changes):
    """A profile with an education, changed as asked."""
    facts = {"first_name": "Jordan", "last_name": "Rivera", "email": "j@example.com",
             "school": "Rensselaer Polytechnic Institute", "degree": "Bachelor's",
             "major": "Computer Science", "graduation": "May 2027"}
    return Profile(**(facts | changes))


def no_claude(_form_field, _facts):
    """Claude never knows."""
    return FieldAnswer("", "claude", 0, "Not asked in this test.")


def education(setting):
    """The fields for a job whose education setting is `setting`."""
    return {f.key: f for f in fields_from_api({"questions": [], "education": setting}, OPTIONS)}


def test_no_education_section_unless_the_api_says_so():
    assert not education("")
    assert not education("education_hidden")


def test_required_education_asks_for_school_degree_major_and_graduation():
    fields = education("education_required")
    required = {key for key, f in fields.items() if f.required}
    assert required == {"school--0", "degree--0", "discipline--0", "end-month--0", "end-year--0"}
    assert fields["degree--0"].options == OPTIONS["degrees"]
    assert fields["end-month--0"].options[4] == "May"
    assert not any(f.required for f in education("education_optional").values())


# What Scale AI's form page says about its Education section
SCALE_CONFIG = {"id": 4666350005, "school_name": "required", "degree": "required",
                "discipline": "hidden", "start_month": "hidden", "start_year": "required",
                "end_month": "hidden", "end_year": "required"}


def test_the_pages_education_config_says_which_boxes_are_shown_and_required():
    job = {"questions": [], "education": "education_required"}
    fields = {f.key: f for f in fields_from_api(job, OPTIONS, SCALE_CONFIG)}
    assert {key: f.required for key, f in fields.items()} == {
        "school--0": True, "degree--0": True, "start-year--0": True, "end-year--0": True}
    optional = fields_from_api(job, OPTIONS, SCALE_CONFIG | {"start_month": "optional"})
    assert [f.required for f in optional if f.key == "start-month--0"] == [False]


def test_reads_the_education_config_from_the_page():
    html = ('<script>window.__remixContext = {"job_post":{"education_config":'
            + json.dumps(SCALE_CONFIG) + ',"questions":[]}};</script>')
    assert education_config_from_page(html) == SCALE_CONFIG
    assert education_config_from_page("<html>no config</html>") is None


def test_a_required_start_year_missing_from_the_profile_is_asked(tmp_path):
    job = {"questions": [], "education": "education_required"}
    form = GreenhouseForm(LINK, job_data=job, education_options=OPTIONS,
                          education_config=SCALE_CONFIG)
    result = ApplyRun(Answerer(profile(), no_claude), tmp_path).run(form)
    assert result.status == "needs_input"
    assert [f.key for f in result.questions] == ["start-year--0"]


def test_profile_answers_use_the_dropdown_wording():
    fields = education("education_required")
    answerer = Answerer(profile(school_start="Aug 2023"), no_claude)
    answers = {key: answerer.answer(f) for key, f in fields.items()}
    assert {key: a.value for key, a in answers.items()} == {
        "school--0": "Rensselaer Polytechnic Institute", "degree--0": "Bachelor's Degree",
        "discipline--0": "Computer Science", "start-month--0": "August",
        "start-year--0": "2023", "end-month--0": "May", "end-year--0": "2027"}


@pytest.mark.parametrize("degree, option", [
    ("Master's", "Master's Degree"), ("Master of Science", "Master's Degree"),
    ("M.S. in Computer Science", "Master's Degree"), ("MEng", "Master's Degree"),
    ("B.S.", "Bachelor's Degree"), ("Bachelor of Arts", "Bachelor's Degree"),
    ("BSc", "Bachelor's Degree"), ("MBA", "Master of Business Administration (M.B.A.)"),
    ("Associate of Science", "Associate's Degree")])
def test_degrees_written_many_ways_find_their_option(degree, option):
    field = education("education_required")["degree--0"]
    assert Answerer(profile(degree=degree), no_claude).answer(field).value == option


def test_a_degree_with_no_clear_option_is_not_guessed():
    """With no matching option, Claude (here, nobody) has to pick."""
    field = education("education_required")["degree--0"]
    assert Answerer(profile(degree="Certificate"), no_claude).answer(field) is None


@pytest.fixture(name="page")
def fixture_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.set_content(PAGE)
        yield page
        browser.close()


def test_picks_the_school_from_the_list(page):
    school = education("education_optional")["school--0"]
    assert GreenhouseForm(LINK).fill(page, school, "rensselaer polytechnic institute") is None
    assert page.locator("#picked-school").inner_text() == "Rensselaer Polytechnic Institute"


def test_picks_other_for_a_school_not_on_the_list(page):
    school = education("education_optional")["school--0"]
    assert GreenhouseForm(LINK).fill(page, school, "Example State University") == "Other"
    assert page.locator("#picked-school").inner_text() == "Other"


def test_fills_the_section_and_skips_boxes_the_form_left_out(tmp_path):
    job = {"questions": [], "education": "education_required"}
    url = tmp_path / "form.html"
    url.write_text(PAGE, encoding="utf-8")
    form = GreenhouseForm(LINK, job_data=job, url=url.as_uri(), education_options=OPTIONS)
    result = ApplyRun(Answerer(profile(school_start="August 2023"), no_claude),
                      tmp_path).run(form)
    assert result.status == "ready", result.reason
    assert [(label, value) for label, value, _ in result.filled] == [
        ("School", "Rensselaer Polytechnic Institute"), ("Degree", "Bachelor's Degree"),
        ("Discipline", "Computer Science"), ("Education end date month", "May"),
        ("Education end date year", "2027")]
