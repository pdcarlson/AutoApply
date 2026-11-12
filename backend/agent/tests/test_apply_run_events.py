"""Tests for the hooks a server uses to watch and stop a run: events, cancel and screenshots."""
import json

from playwright.sync_api import Browser, BrowserType

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.runner.apply_run import ApplyRun
from agent.settings import AGENT_DIR
from agent.tests.test_greenhouse import example_profile, fake_claude, fake_form

WHY_HERE = "I like building tools people use."


class Recorder:
    """Collects every on_event call as (kind, data)."""

    def __init__(self):
        self.events = []

    def __call__(self, kind, **data):
        self.events.append((kind, data))

    def kinds(self):
        """Return the events as short strings like 'phase:opening' or 'field'."""
        return [f"phase:{data['name']}" if kind == "phase" else kind for kind, data in self.events]


def spy_on_browsers(monkeypatch):
    """Record how each browser is launched and whether it's closed."""
    seen = {"launch": [], "closed": 0}
    launch, close = BrowserType.launch, Browser.close

    def spy_launch(self, *args, **kwargs):
        seen["launch"].append(kwargs)
        return launch(self, *args, **kwargs)

    def spy_close(self, *args, **kwargs):
        seen["closed"] += 1
        return close(self, *args, **kwargs)

    monkeypatch.setattr(BrowserType, "launch", spy_launch)
    monkeypatch.setattr(Browser, "close", spy_close)
    return seen


def test_events_arrive_in_order_and_filled_screenshot_is_taken(tmp_path):
    """A dry run reports opening, then filling, then field/filled pairs, and saves -filled.png."""
    events = Recorder()
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, on_event=events)
    result = run.run(fake_form(), shot_name="job-1")

    assert result.status == "ready", result.reason
    kinds = events.kinds()
    assert kinds[:2] == ["phase:opening", "phase:filling"]
    assert kinds[2:] == ["field", "filled"] * len(result.filled)
    filled_events = [data for kind, data in events.events if kind == "filled"]
    assert [(e["label"], e["value"], e["source"], e["confidence"]) for e in filled_events] \
        == result.filled_detail
    field_labels = [data["label"] for kind, data in events.events if kind == "field"]
    assert field_labels == [label for label, _value, _source in result.filled]

    shot = tmp_path / "job-1-filled.png"
    assert shot.exists()
    assert result.filled_screenshot == result.screenshot == str(shot)
    assert not (tmp_path / "job-1-result.png").exists()
    assert len(result.answered) == len(result.filled)


def test_submit_takes_both_screenshots_and_reports_its_phases(tmp_path, monkeypatch):
    """Submitting saves -filled.png before Submit and -result.png after, and passes slow_mo on."""
    seen = spy_on_browsers(monkeypatch)
    events = Recorder()
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, submit=True,
                   on_event=events, slow_mo=5)
    result = run.run(fake_form())

    assert result.status == "submitted", result.reason
    assert events.kinds()[-2:] == ["phase:submitting", "phase:confirming"]
    assert result.filled_screenshot == str(tmp_path / "fakecompany-1001-filled.png")
    assert result.screenshot == str(tmp_path / "fakecompany-1001-result.png")
    assert (tmp_path / "fakecompany-1001-filled.png").exists()
    assert (tmp_path / "fakecompany-1001-result.png").exists()
    assert seen["launch"][0]["slow_mo"] == 5


def test_should_stop_cancels_and_closes_the_browser(tmp_path, monkeypatch):
    """Asking to stop partway through the fill ends the run as cancelled with the browser closed."""
    seen = spy_on_browsers(monkeypatch)
    events = Recorder()
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, submit=True,
                   on_event=events,
                   should_stop=lambda: events.kinds().count("filled") >= 2)
    result = run.run(fake_form())

    assert result.status == "cancelled"
    assert result.reason == "Cancelled."
    assert len(result.filled) == 2
    assert len(seen["launch"]) == seen["closed"] == 1
    assert "phase:submitting" not in events.kinds()
    assert not list(tmp_path.glob("*.png"))


def test_should_stop_before_the_browser_opens(tmp_path, monkeypatch):
    """A stop that's already requested ends the run without launching a browser."""
    seen = spy_on_browsers(monkeypatch)
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path,
                   should_stop=lambda: True)
    result = run.run(fake_form())
    assert result.status == "cancelled"
    assert not seen["launch"]


def test_answered_is_filled_on_needs_input(tmp_path):
    """When the run stops on a question, it still returns every answer it planned."""
    result = ApplyRun(Answerer(example_profile(), fake_claude), tmp_path).run(fake_form())
    assert result.status == "needs_input"
    planned = {form_field.label: answer for form_field, answer in result.answered}
    assert planned["First Name"].source == "profile"
    sponsorship = ("Will you now or in the future require visa sponsorship to work in the "
                   "United States?")
    assert (planned[sponsorship].value, planned[sponsorship].source) == ("No", "claude")
    assert planned[sponsorship].confidence == 95
    assert "Why do you want to work here?" not in planned
    assert not result.filled


def test_unknown_yes_no_facts_and_extra_facts():
    """Facts the applicant didn't give read as Unknown, and extra facts reach Claude."""
    profile = Profile("Ada", "Lovelace", "ada@example.com", work_authorized_us=None,
                      needs_sponsorship=None, willing_to_relocate=None,
                      extra_facts=["Skills: Python, SQL", "Relocation: depends on the role"])
    facts = profile.facts()
    assert "Authorized to work in the United States: Unknown (ask the applicant)" in facts
    assert "Needs visa sponsorship now or in the future: Unknown (ask the applicant)" in facts
    assert "Willing to relocate: Unknown (ask the applicant)" in facts
    assert facts.splitlines()[-2:] == ["Skills: Python, SQL", "Relocation: depends on the role"]


def test_save_leaves_out_empty_extra_facts(tmp_path):
    """Saving the example profile never adds an extra_facts key, and a set one round-trips."""
    profile = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
    profile.save(tmp_path / "profile.json")
    assert "extra_facts" not in json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))

    profile.extra_facts = ["Skills: Python"]
    profile.save(tmp_path / "with_facts.json")
    assert Profile.load(tmp_path / "with_facts.json").extra_facts == ["Skills: Python"]


def test_save_without_a_resume(tmp_path):
    """A profile with no resume saves without crashing."""
    Profile("Ada", "Lovelace", "ada@example.com").save(tmp_path / "profile.json")
    data = json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    assert data["resume_path"] == ""
