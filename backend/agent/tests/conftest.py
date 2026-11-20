"""Fixtures the agent's tests share."""
import pytest

from agent.answers.answerer import Answerer
from agent.runner.apply_run import ApplyRun
from agent.tests.helpers import WHY_HERE, example_profile, fake_claude, fake_form


@pytest.fixture(name="holding")
def fixture_holding(tmp_path):
    """Return fill(form=None, **ApplyRun options) -> RunResult, closing every held browser after.

    A HeldForm never closes its own window, so the test's held windows are closed here.
    """
    opened = []

    def fill(form=None, **options):
        """Fill the form with hold=True and remember the held window."""
        run = ApplyRun(Answerer(example_profile(WHY_HERE), fake_claude), tmp_path, hold=True,
                       **options)
        result = run.run(form or fake_form(), shot_name="job-1")
        if result.held is not None:
            opened.append(result.held)
        return result
    yield fill
    for held in opened:
        held.close()
