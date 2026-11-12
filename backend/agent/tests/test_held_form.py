"""Tests for holding a filled form open and submitting it later, on the local fake form only.

The fake page's query string picks a variant: ?confirm_ms=N confirms N ms after Submit, and
?code=1 asks for an emailed verification code instead of confirming (its Verify button, or
confirm_ms running out, shows the thank-you page).

A HeldForm never closes its own window, so every test closes what it opened (`holding`).
"""
import time

import pytest

from agent.answers.answerer import Answerer
from agent.runner.apply_run import FORM_GONE, WINDOW_CLOSED, ApplyRun
from agent.tests.test_apply_run_events import WHY_HERE, Recorder, spy_on_browsers
from agent.tests.test_greenhouse import example_profile, fake_claude, fake_form


def variant(query):
    """The fake form, with a test-only variant picked by `query`."""
    form = fake_form()
    form.url += f"?{query}"
    return form


@pytest.fixture
def holding(tmp_path):
    """fill(form=None, **ApplyRun kwargs) -> RunResult; every held browser is closed afterwards."""
    opened = []

    def fill(form=None, **kwargs):
        run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, hold=True,
                       **kwargs)
        result = run.run(form or fake_form(), shot_name="job-1")
        if result.held is not None:
            opened.append(result.held)
        return result
    yield fill
    for held in opened:
        held.close()


def test_hold_keeps_the_browser_open_and_submit_uses_it(tmp_path, monkeypatch, holding):
    """A held fill stays open; submit presses Submit on that page without filling it again,
    saves the confirmation screenshot, and still leaves closing to the caller."""
    seen = spy_on_browsers(monkeypatch)
    result = holding()
    assert result.status == "ready", result.reason
    held = result.held
    assert held is not None and held.usable()
    assert seen["closed"] == 0 and len(seen["launch"]) == 1

    events = Recorder()
    sent = held.submit(on_event=events)
    assert sent.status == "submitted" and sent.pressed, sent.reason
    assert events.kinds() == ["phase:submitting", "phase:confirming"]  # no filling
    assert sent.filled_detail == result.filled_detail
    assert sent.filled_screenshot == str(tmp_path / "job-1-filled.png")
    assert sent.screenshot == str(tmp_path / "job-1-result.png")
    assert (tmp_path / "job-1-result.png").exists()
    assert seen["closed"] == 0 and not held.closed and held.window_open()
    held.close()
    assert seen["closed"] == 1 and not held.window_open()


def test_a_closed_window_is_not_usable(holding):
    """Closing the page (as a person closing the window would) makes the held form unusable."""
    held = holding().held
    held.page.close()
    assert not held.window_open() and not held.usable()
    held.close()
    held.close()  # twice is fine


def test_no_hold_for_a_run_that_doesnt_end_ready(monkeypatch, holding):
    """Cancelled runs close their browser even with hold=True."""
    seen = spy_on_browsers(monkeypatch)
    events = Recorder()
    result = holding(on_event=events,
                     should_stop=lambda: events.kinds().count("filled") >= 1)
    assert result.status == "cancelled" and result.held is None
    assert seen["closed"] == 1


def test_waits_for_a_late_confirmation(holding):
    """The confirmation is polled for until it shows up, well past one poll."""
    held = holding(form=variant("confirm_ms=2500")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=20)
    took = time.monotonic() - started
    assert sent.status == "submitted", sent.reason
    assert 2.4 < took < 10


def test_code_prompt_then_timeout_keeps_the_window(tmp_path, holding):
    """No confirmation in time while the site asks for a code: failed and says so, but the
    window stays open on the code prompt, and a code entered later still confirms it."""
    held = holding(form=variant("code=1")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=2)
    assert 1.9 < time.monotonic() - started < 10
    assert sent.status == "failed" and sent.asked_for_code and sent.pressed
    assert "verification code" in sent.reason
    assert (tmp_path / "job-1-result.png").exists()
    assert not held.closed and held.window_open() and not held.confirmed()

    held.page.click("#verify")  # the person types the code after the timeout
    assert held.confirmed() and held.window_open()


def test_code_prompt_then_confirmed(holding):
    """A code typed in during the wait (here: the page confirms by itself) counts as sent."""
    held = holding(form=variant("code=1&confirm_ms=1500")).held
    sent = held.submit(confirm_timeout_s=20)
    assert sent.status == "submitted" and not sent.asked_for_code


def test_should_stop_before_submit_presses_nothing(holding):
    held = holding().held
    events = Recorder()
    sent = held.submit(on_event=events, should_stop=lambda: True)
    assert sent.status == "cancelled" and not events.events and not sent.pressed
    assert held.usable()  # still open, still filled


def test_abort_stops_the_wait(holding):
    """should_abort() ends the confirmation wait early; the window stays."""
    held = holding(form=variant("code=1")).held
    started = time.monotonic()
    sent = held.submit(confirm_timeout_s=60, should_abort=lambda: True)
    assert time.monotonic() - started < 10
    assert sent.status == "failed" and sent.pressed and held.window_open()


def test_window_closed_while_waiting(holding):
    """The person closes the window during the wait: failed, window_closed, and it says so."""
    held = holding(form=variant("code=1")).held
    sent = held.submit(confirm_timeout_s=60,
                       should_abort=lambda: held.page.close() or False)
    assert sent.status == "failed" and sent.window_closed and sent.reason == WINDOW_CLOSED


def test_a_page_already_confirmed_is_not_pressed_again(holding):
    """The person pressed Submit in the window themselves: nothing is pressed, it's submitted."""
    held = holding().held
    held.page.get_by_role("button", name="Submit application").click()
    assert held.confirmed()
    events = Recorder()
    sent = held.submit(on_event=events)
    assert sent.status == "submitted" and not sent.pressed and not events.events


def test_a_page_without_the_form_is_left_alone(holding):
    """The window shows something else (no form, no confirmation): nothing pressed."""
    held = holding().held
    held.page.evaluate("document.body.innerHTML = '<p>Somewhere else</p>'")
    sent = held.submit()
    assert sent.status == "failed" and not sent.pressed and sent.reason == FORM_GONE
    assert held.window_open()


def test_submit_run_without_hold_still_confirms(tmp_path):
    """The CLI path (submit=True, no hold) waits for a late confirmation too."""
    run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, submit=True)
    result = run.run(variant("confirm_ms=1000"))
    assert result.status == "submitted", result.reason
    assert result.held is None
