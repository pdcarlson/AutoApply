"""Tests for the terminal agent's review step, which presses Submit only after "submit"."""
from agent.__main__ import review_and_submit
from agent.tests.helpers import variant


def answers(monkeypatch, *replies):
    """Feed these replies to input(), and record the prompts."""
    prompts, queue = [], list(replies)

    def fake_input(prompt=""):
        """Record the prompt and give the next reply."""
        prompts.append(prompt)
        return queue.pop(0)
    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def test_typing_submit_sends_it_and_closes_after_the_screenshot(tmp_path, monkeypatch, holding):
    """Typing "submit" sends it, and the window closes only after the confirmation screenshot."""
    filled = holding()
    held = filled.held
    prompts = answers(monkeypatch, "submit")
    result = review_and_submit(filled)
    assert result.status == "submitted", result.reason
    assert (tmp_path / "job-1-result.png").exists()
    assert held.closed
    assert len(prompts) == 1  # no "press Enter to close" prompt after a confirmed submit


def test_pressing_enter_sends_nothing_and_keeps_the_window_until_you_say(monkeypatch, holding):
    """Pressing Enter sends nothing, and the window stays open until the second Enter."""
    filled = holding()
    held = filled.held
    seen_open = []
    prompts = answers(monkeypatch, "", "")
    monkeypatch.setattr(held, "submit", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    original_close = held.close

    def close():
        """Record whether the window was open, then close it."""
        seen_open.append(held.window_open())
        original_close()
    monkeypatch.setattr(held, "close", close)
    result = review_and_submit(filled)
    assert result.status == "ready"
    assert "not sent" in result.reason
    assert len(prompts) == 2  # "type submit", then "press Enter when you're done with it"
    assert seen_open == [True]  # the window was still open until that second Enter


def test_waits_past_the_timeout_for_a_code_and_records_the_confirmation(tmp_path, monkeypatch,
                                                                        holding):
    """The site asks for an emailed code; the agent keeps waiting after its timeout, and records
    the application once the thank-you page appears (here, 3 s later)."""
    filled = holding(form=variant("code=1&confirm_ms=3000"), confirm_timeout_s=0.5)
    held = filled.held
    prompts = answers(monkeypatch, "submit")
    result = review_and_submit(filled)
    assert result.status == "submitted", result.reason
    assert (tmp_path / "job-1-result.png").exists()
    assert held.closed
    assert len(prompts) == 1
