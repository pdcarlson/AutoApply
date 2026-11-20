"""Builds what one run needs: the job's form, a fresh profile and answerer, and the browser."""
from collections.abc import Callable

from agent.answers.answerer import Answerer
from agent.browser import LocalBrowser, RemoteBrowser
from agent.runner.apply_run import ApplyRun
from server import jobs
from server.agent_bridge import cached_claude, make_form, no_claude
from server.agent_profile import build_agent_profile
from server.answer_bank import AnswerBank
from server.answer_sources import SourceMap
from server.config import Config
from server.runs.run_context import RunContext
from server.store import Store


class RunSetup:
    """Prepares runs for one user's worker, from their store, Answer bank and the config."""

    def __init__(self, store: Store, bank: AnswerBank, config: Config):
        self.store = store
        self.bank = bank
        self.config = config

    def prepare(self, job_id: str, run_id: str) -> RunContext:
        """Build a fresh profile, answerer (with the job's Claude cache) and form for one run.

        Raises UnsupportedLink for sites the agent can't fill, and KeyError if the job is gone.
        """
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is None:
                raise KeyError(job_id)
            snapshot = {"internal": dict(job["internal"]), "company": job.get("company", "")}
            threshold = int(db.settings["confidenceThreshold"])
        form = make_form(snapshot)
        profile, ids = build_agent_profile(self.store, self.bank, snapshot["company"])
        ask = cached_claude(self.store, job_id) if self.config.claude_enabled else no_claude
        answerer = Answerer(profile, ask, threshold=threshold)
        return RunContext(job_id, run_id, snapshot["company"], form, profile, answerer,
                          SourceMap.build(self.bank, ids))

    def apply_run(self, ctx: RunContext, on_event: Callable,
                  should_stop: Callable[[], bool]) -> ApplyRun:
        """Return the agent's ApplyRun for `ctx`: it fills the form and holds it, never submits."""
        return ApplyRun(
            ctx.answerer, self.store.dir("screenshots"), submit=False,
            show=self.config.show_browser, slow_mo=self.config.slow_mo_ms,
            on_event=on_event, should_stop=should_stop, hold=True,
            confirm_timeout_s=self.config.confirm_timeout_s, browser=self.browser_source())

    def browser_source(self) -> LocalBrowser | RemoteBrowser:
        """Return where runs get their browser: BROWSER_CDP_URL's, or one launched here."""
        if self.config.browser_cdp_url:
            return RemoteBrowser(self.config.browser_cdp_url, slow_mo=self.config.slow_mo_ms)
        return LocalBrowser(show=self.config.show_browser, slow_mo=self.config.slow_mo_ms)
