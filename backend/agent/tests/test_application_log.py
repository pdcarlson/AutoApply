"""Tests for the application log."""
import pytest

from agent.jobs.application_log import ApplicationLog, DuplicateLink
from agent.jobs.job_link import JobLink
from agent.runner.apply_run import RunResult

LINK = JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/12345")


def test_add_creates_a_record(tmp_path):
    """A new link gets a record, and it's saved to disk."""
    log = ApplicationLog(tmp_path / "applications.json")
    log.add(LINK)
    assert ApplicationLog(tmp_path / "applications.json").find(LINK)["status"] == "started"


def test_submitted_job_is_a_duplicate(tmp_path):
    """A job that was already submitted can't be added again."""
    log = ApplicationLog(tmp_path / "applications.json")
    log.add(LINK)
    log.update(LINK, RunResult("submitted"))
    with pytest.raises(DuplicateLink):
        log.add(LINK)


def test_unfinished_job_can_run_again(tmp_path):
    """A dry run or a failed run can be tried again."""
    log = ApplicationLog(tmp_path / "applications.json")
    log.add(LINK)
    log.update(LINK, RunResult("ready"))
    log.add(LINK)
    assert len(log.records) == 1
