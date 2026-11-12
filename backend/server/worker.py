"""The AgentWorker: one background thread that works the queue one job at a time (spec 2.7).

Each tick: `promote_waiting`, then (unless paused) the first `queued` id in `state.queue` becomes
`running/opening` and `run_job` fills it with the agent's `ApplyRun` and sync Playwright. The
browser is launched inside the thread that runs the job and never leaves it. The first fill
never presses Submit: it ends at `needs_input`, `handoff`, `ready` or (on failure) `open`.

Runs and ownership: claiming a job sets `internal.runId`. Cancel, skip and DELETE /account
detach the job (runId -> None); `should_stop` notices before the next field and the run's
result is dropped. Event and result handlers only touch a job their run still owns.

Building blocks WP5 reuses for POST /jobs/:id/submit (inline in the request thread):

    with store.tx() as db:            # require `ready`, then claim it
        run_id = worker.claim(job, phase="submitting")
    ctx = worker.prepare(job_id, run_id)       # fresh profile, answerer, form; Claude cache kept
    result = worker.execute(ctx, submit=True)  # phases submitting/confirming; keeps `fields`
"""
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile, normalize
from agent.forms.form_field import FormField
from agent.jobs.job_link import UnsupportedLink
from agent.runner.apply_run import ApplyRun, RunResult
from server import jobs, questions
from server.agent_bridge import SourceMap, build_agent_profile, cached_claude, make_form
from server.answer_bank import AnswerBank
from server.config import Config
from server.store import Store, iso, new_id

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
STOP_TIMEOUT_SECONDS = 30.0
SITE_NAMES = {"greenhouse": "Greenhouse", "ashby": "Ashby", "lever": "Lever"}
MISSING_RESUME = "This form needs a resume. Add one on your Profile page."


@dataclass
class RunContext:  # pylint: disable=too-many-instance-attributes
    """Everything one run of one job needs, built by `AgentWorker.prepare`."""

    job_id: str
    run_id: str
    company: str
    form: object
    profile: Profile
    answerer: Answerer
    sources: SourceMap
    fields: list[FormField] = field(default_factory=list)  # filled in after read_fields

    def field_by_label(self, label: str) -> FormField | None:
        wanted = normalize(label)
        return next((f for f in self.fields if normalize(f.label) == wanted), None)


class AgentWorker:  # pylint: disable=too-many-instance-attributes
    """Same interface as server.app.NullWorker: start, stop, wake, cancel_current, run_next."""

    def __init__(self, store: Store, bank: AnswerBank, config: Config,
                 poll_seconds: float = POLL_SECONDS):
        self.store = store
        self.bank = bank
        self.config = config
        self.poll_seconds = poll_seconds
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._wake = threading.Event()
        self._run_lock = threading.Lock()  # one fill at a time
        self._active: set[str] = set()  # run ids in progress (fill or submit)
        self._cancelled: set[str] = set()  # run ids cancel_current() stopped

    # ----- thread lifecycle -----

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._loop, name="agent-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the loop; a run in progress stops at its next field and goes back in line."""
        self._stopping.set()
        self._wake.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(STOP_TIMEOUT_SECONDS)

    def wake(self) -> None:
        self._wake.set()

    def cancel_current(self) -> None:
        """Asks every run in progress to stop at the next field (DELETE /account)."""
        self._cancelled.update(self._active)

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                while not self._stopping.is_set() and self.run_next():
                    pass
            except Exception:  # pylint: disable=broad-except
                log.exception("The agent worker hit an error; it keeps going")
            self._wake.wait(self.poll_seconds)
            self._wake.clear()

    # ----- picking and claiming -----

    def claim(self, job: dict, phase: str = "opening") -> str:
        """Marks `job` running and owned by a new run; returns the run id.

        Call inside the `store.tx()` that checked the job's state, so the move is atomic.
        """
        run_id = new_id("run")
        job.update(state="running", phase=phase, currentField=None)
        job["internal"]["runId"] = run_id
        job["internal"]["cancelRequested"] = False
        self._active.add(run_id)
        return run_id

    def run_next(self) -> str | None:
        """Promotes waiting jobs, then fills the next queued job (unless paused).

        Returns the id of the job it ran, or None when there was nothing to do.
        """
        if self._stopping.is_set() or not self._run_lock.acquire(blocking=False):  # pylint: disable=consider-using-with
            return None
        try:
            with self.store.tx() as db:
                jobs.promote_waiting(db, self.store.now())
                if db.state.get("paused"):
                    return None
                job = next((j for jid in db.state.get("queue", [])
                            if (j := jobs.find(db, jid)) is not None
                            and j.get("state") == "queued"), None)
                if job is None:
                    return None
                jobs.reset_progress(job)
                job["question"] = None
                job["internal"]["question"] = None
                run_id = self.claim(job)
                job_id = job["id"]
            self.run_job(job_id, run_id)
            return job_id
        finally:
            self._run_lock.release()

    # ----- one run -----

    def prepare(self, job_id: str, run_id: str) -> RunContext:
        """A fresh profile, answerer (with the job's Claude cache) and form for one run.

        Raises UnsupportedLink for sites the agent can't fill, and KeyError if the job is gone.
        """
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is None:
                raise KeyError(job_id)
            snapshot = {"internal": dict(job["internal"]), "company": job.get("company", "")}
            threshold = int(db.settings["confidenceThreshold"])
        form = make_form(snapshot, self.config)
        profile, ids = build_agent_profile(self.store, self.bank, snapshot["company"])
        answerer = Answerer(profile, cached_claude(self.store, job_id), threshold=threshold)
        return RunContext(job_id, run_id, snapshot["company"], form, profile, answerer,
                          SourceMap.build(self.bank, ids))

    def execute(self, ctx: RunContext, submit: bool = False) -> RunResult:
        """Runs ApplyRun for `ctx`. Progress events update the job while its run owns it.

        With `submit=False` (a fill) the job's `fields` are rebuilt as fields are filled. With
        `submit=True` (WP5) only `phase` (submitting, confirming) and `currentField` change, so
        the fields shown at review time stay put.
        """
        try:
            ctx.fields = ctx.form.read_fields()
        except Exception:  # pylint: disable=broad-except
            ctx.fields = []  # ApplyRun reads them again and reports the error
        run = ApplyRun(
            ctx.answerer, self.store.dir("screenshots"), submit=submit,
            show=self.config.show_browser, slow_mo=self.config.slow_mo_ms,
            on_event=lambda kind, **data: self._on_event(ctx, submit, kind, data),
            should_stop=lambda: self.should_stop(ctx))
        self._active.add(ctx.run_id)
        try:
            return run.run(ctx.form, shot_name=ctx.job_id)
        finally:
            self._active.discard(ctx.run_id)
            self._cancelled.discard(ctx.run_id)

    def should_stop(self, ctx: RunContext) -> bool:
        if self._stopping.is_set() or ctx.run_id in self._cancelled:
            return True
        with self.store.tx() as db:
            job = jobs.find(db, ctx.job_id)
            return job is None or not self._owns(job, ctx.run_id)

    @staticmethod
    def _owns(job: dict, run_id: str) -> bool:
        internal = job.get("internal") or {}
        return job.get("state") == "running" and internal.get("runId") == run_id \
            and not internal.get("cancelRequested")

    def _on_event(self, ctx: RunContext, submit: bool, kind: str, data: dict) -> None:
        with self.store.tx() as db:
            job = jobs.find(db, ctx.job_id)
            if job is None or not self._owns(job, ctx.run_id):
                return
            if kind == "phase":
                if not submit or data["name"] in ("submitting", "confirming"):
                    job["phase"] = data["name"]
            elif kind == "field":
                job["currentField"] = data["label"]
            elif kind == "filled":
                job["currentField"] = None
                if not submit:
                    job.setdefault("fields", []).append(ctx.sources.filled_field(
                        ctx.field_by_label(data["label"]), data["label"], data["value"],
                        data["source"], data["confidence"]))
                    job["progress"] = {**job["progress"], "filled": len(job["fields"])}

    def run_job(self, job_id: str, run_id: str) -> str | None:
        """Fills one claimed job up to `needs_input`, `handoff` or `ready` (never submits).

        Returns the job's state afterwards, or None when the run no longer owned the job.
        """
        try:
            ctx = self.prepare(job_id, run_id)
        except KeyError:
            return None
        except UnsupportedLink:
            return self._finish(job_id, run_id, lambda db, job: self._to_handoff(
                db, job, self._unsupported_reason(job)))
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Couldn't prepare job %s", job_id)
            return self._finish(job_id, run_id, lambda db, job: self._to_failed(
                db, job, f"Couldn't start: {error}"))
        try:
            result = self.execute(ctx, submit=False)
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Run for job %s crashed", job_id)
            result = RunResult("failed", f"The agent crashed: {error}")
        return self._finish(job_id, run_id, lambda db, job: self._apply_result(db, job, ctx,
                                                                               result))

    def _finish(self, job_id: str, run_id: str, apply) -> str | None:
        """Applies a run's outcome under the lock, if the run still owns the job."""
        self._active.discard(run_id)
        self._cancelled.discard(run_id)
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is None:
                return None
            if not self._owns(job, run_id):
                if job.get("state") == "open":  # cancelled mid-run: drop what it filled
                    jobs.reset_progress(job)
                return None
            apply(db, job)
            job["internal"]["runId"] = None
            job["internal"]["cancelRequested"] = False
            return job["state"]

    # ----- outcomes -----

    @staticmethod
    def _unsupported_reason(job: dict) -> str:
        site = (job["internal"].get("link") or {}).get("site", "")
        return f"AutoApply can't fill {SITE_NAMES.get(site, site.title())} forms yet"

    def _apply_result(self, db, job: dict, ctx: RunContext, result: RunResult) -> None:
        if result.status == "needs_input":
            self._to_question(db, job, ctx, result)
        elif result.status == "ready":
            self._to_ready(db, job, ctx, result)
        elif result.status == "cancelled":
            # The run still owns the job, so the worker is shutting down: put it back in line.
            jobs.reset_progress(job)
            jobs.requeue_at_front(db, job)
        else:
            self._to_failed(db, job, result.reason or "The run didn't finish.")

    def _to_question(self, db, job: dict, ctx: RunContext, result: RunResult) -> None:
        form_field = result.questions[0]
        if form_field.kind == "file":
            if form_field.profile_key == "resume_path" and not ctx.profile.resume_path:
                self._to_failed(db, job, MISSING_RESUME)
            else:
                self._to_handoff(db, job, "This form needs a file the agent doesn't have: "
                                 f"{form_field.label}")
            return
        now = self.store.now_iso()
        internal = job["internal"]
        internal["questionCount"] = int(internal.get("questionCount") or 0) + 1
        guess = ctx.answerer.claude_answers.get(form_field.key)
        question, internal["question"] = questions.make_question(
            job["id"], internal["questionCount"], form_field, guess)
        planned = ctx.sources.from_answered(result.answered)
        total = len(ctx.fields) or len(result.answered) + len(result.questions)
        job.update(state="needs_input", phase=None, currentField=None, question=question,
                   fields=planned, progress={"filled": len(planned), "total": total})
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, "amber", f"Paused on a question: {form_field.label}", now)

    def _to_ready(self, db, job: dict, ctx: RunContext, result: RunResult) -> None:
        now = self.store.now_iso()
        filled = [ctx.sources.filled_field(ctx.field_by_label(label), label, value, source,
                                           confidence)
                  for label, value, source, confidence in result.filled_detail]
        count = len(filled)
        job.update(state="ready", readyAt=now, phase=None, currentField=None, question=None,
                   fields=filled, progress={"filled": count, "total": count})
        job["internal"]["question"] = None
        job["internal"]["screenshot"] = Path(result.filled_screenshot).name \
            if result.filled_screenshot else None
        for label, _value, source, _confidence in result.filled_detail:
            record = ctx.sources.record_for(label) if source == "saved" else None
            if record is not None:
                self.bank.record_use(record["id"], ctx.company, label)
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, "muted", "Filled and held for your review", now)

    def _to_handoff(self, db, job: dict, reason: str) -> None:
        job.update(state="handoff", phase=None, currentField=None, question=None, reason=reason)
        job["internal"]["question"] = None
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, "amber", reason, self.store.now_iso())

    def _to_failed(self, db, job: dict, reason: str) -> None:
        """Back to `open` (there is no failed state), with a `bad` check and the reason."""
        jobs.reset_progress(job)
        checks = [c for c in job.get("checks") or [] if c.get("status") != "bad"]
        job.update(state="open", question=None, checks=[{"status": "bad", "text": reason}]
                   + checks, reason=f"Last try didn't finish: {reason}")
        job["internal"]["question"] = None
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, "red", f"Last try didn't finish: {reason}", iso(self.store.now()))
