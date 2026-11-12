"""Tests for holding a filled form open and submitting it later, on the local fake form only.

The fake page's query string picks a variant: ?confirm_ms=N confirms N ms after Submit, and
?code=1 asks for an emailed verification code instead of confirming.
"""
import time

from agent.answers.answerer import Answerer
from agent.runner.apply_run import ApplyRun
from agent.tests.test_apply_run_events import WHY_HERE, Recorder, spy_on_browsers
from agent.tests.test_greenhouse import example_profile, fake_claude, fake_form


def variant(query):
    """The fake form, with a test-only variant picked by `query`."""
    form = fake_form()
    form.url += f"?{query}"
    return form


def fill_and_hold(tmp_path, form=None, **kwargs):
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, hold=True,
                   **kwargs)
    return run.run(form or fake_form(), shot_name="job-1")


def test_hold_keeps_the_browser_open_and_submit_uses_it(tmp_path, monkeypatch):
    """A held fill stays open; submit presses Submit on that page without filling it again."""
    seen = spy_on_browsers(monkeypatch)
    result = fill_and_hold(tmp_path)
    assert result.status == "ready", result.reason
    held = result.held
    assert held is not None and held.usable()
    assert seen["closed"] == 0 and len(seen["launch"]) == 1

    events = Recorder()
    sent = held.submit(on_event=events)
    assert sent.status == "submitted", sent.reason
    assert events.kinds() == ["phase:submitting", "phase:confirming"]  # no filling
    assert sent.filled_detail == result.filled_detail
    assert sent.filled_screenshot == str(tmp_path / "job-1-filled.png")
    assert sent.screenshot == str(tmp_path / "job-1-result.png")
    assert (tmp_path / "job-1-result.png").exists()
    assert seen["closed"] == 1 and len(seen["launch"]) == 1 and held.closed
    assert not held.usable()


def test_a_closed_window_is_not_usable(tmp_path):
    """Closing the page (as a person closing the window would) makes the held form unusable."""
    held = fill_and_hold(tmp_path).held
    held.page.close()
    assert not held.usable()
    held.close()
    held.close()  # twice is fine


def test_no_hold_for_a_run_that_doesnt_end_ready(tmp_path, monkeypatch):
    """Cancelled runs close their browser even with hold=True."""
    seen = spy_on_browsers(monkeypatch)
    events = Recorder()
    result = fill_and_hold(tmp_path, on_event=events,
                           should_stop=lambda: events.kinds().count("filled") >= 1)
    assert result.status == "cancelled" and result.held is None
    assert seen["closed"] == 1


def test_waits_for_a_late_confirmation(tmp_path):
    """The confirmation is polled for until it shows up, well past one poll."""
    held = fill_and_hold(tmp_path, form=variant("confirm_ms=2500")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=20)
    took = time.monotonic() - started
    assert sent.status == "submitted", sent.reason
    assert 2.4 < took < 10


def test_code_prompt_then_timeout(tmp_path):
    """No confirmation in time while the site asks for an emailed code: failed, and it says so."""
    held = fill_and_hold(tmp_path, form=variant("code=1")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=2)
    assert 1.9 < time.monotonic() - started < 10
    assert sent.status == "failed" and sent.asked_for_code
    assert "verification code" in sent.reason
    assert (tmp_path / "job-1-result.png").exists() and held.closed


def test_code_prompt_then_confirmed(tmp_path):
    """A code typed in during the wait (here: the page confirms by itself) counts as sent."""
    held = fill_and_hold(tmp_path, form=variant("code=1&confirm_ms=1500")).held
    sent = held.submit(confirm_timeout_s=20)
    assert sent.status == "submitted" and not sent.asked_for_code


def test_should_stop_before_submit_presses_nothing(tmp_path):
    held = fill_and_hold(tmp_path).held
    events = Recorder()
    sent = held.submit(on_event=events, should_stop=lambda: True)
    assert sent.status == "cancelled" and not events.events and held.closed


def test_abort_stops_the_wait(tmp_path):
    """should_abort() ends the confirmation wait early."""
    held = fill_and_hold(tmp_path, form=variant("code=1")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=60, should_abort=lambda: True)
    assert time.monotonic() - started < 10
    assert sent.status == "failed"


def test_submit_run_without_hold_still_confirms(tmp_path):
    """The CLI path (submit=True, no hold) waits for a late confirmation too."""
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, submit=True)
    result = run.run(variant("confirm_ms=1000"))
    assert result.status == "submitted", result.reason
    assert result.held is None
