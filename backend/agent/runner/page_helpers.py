"""Small helpers for saving screenshots and closing the browser."""
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from agent.runner.run_result import RunResult


def take_screenshot(page, path: Path, result: RunResult) -> bool:
    """Save a full-page screenshot and record it as the run's latest one. True if saved."""
    try:
        page.screenshot(path=path, full_page=True)
        result.screenshot = str(path)
        return True
    except PlaywrightError:
        return False


def close_quietly(close) -> None:
    """Run a close/stop call, ignoring a browser or driver that's already gone."""
    try:
        close()
    except Exception:  # pylint: disable=broad-except  # a dead driver raises its own error types
        pass
