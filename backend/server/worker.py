"""The AgentWorker: one background thread that works the queue one job at a time (spec 2.7).

Each tick: `promote_waiting`, then (unless paused) the first `queued` id in `state.queue` becomes
`running/opening` and `run_job` fills it with the agent's `ApplyRun` and sync Playwright. The
browser is launched inside the thread that runs the job and never leaves it. The first fill
never presses Submit: it ends at `needs_input`, `handoff`, `ready` or (on failure) `open`.

Runs and ownership: claiming a job sets `internal.runId`. Cancel, skip and DELETE /account
detach the job (runId -> None); `should_stop` notices before the next field and the run's
result is dropped. Event and result handlers only touch a job their run still owns.

Held forms: each fill runs on its own `FormSession` thread (server.held_forms), because sync
Playwright objects can't leave the thread that made them. A fill that ends `ready` keeps its
browser open on that thread, in `self.forms`, and the worker moves on to the next job. Submit
presses Submit on that page; without one (restart, or the person closed the window) it fills
the form again first, in a window that is held the same way. The worker never closes a held
window (see server.held_forms for the only closes): skip, cancel and DELETE /account leave it
open, and a job applied to again while its window is still open goes straight back to `ready`
on it. A window still waiting for its confirmation after Submit is watched with no time limit;
when the thank-you page shows up the application is recorded (`_on_window_confirmed`).

One browser run at a time: every fill and submit holds `_run_lock`. POST /jobs/:id/submit runs
in the request thread (the request answers once the submit is done) through `submit_run`, which
waits for a fill in progress to finish and keeps the loop from starting the next fill meanwhile:

    with store.tx() as db:            # require `ready`, then claim it
        run_id = worker.claim(job, phase="submitting")
    outcome = worker.submit_run(job_id, run_id)  # the held page, or a fresh fill; keeps `fields`
"""
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile, normalize
from agent.forms.form_field import FormField
from agent.jobs.job_link import UnsupportedLink
from agent.runner.apply_run import ApplyRun, RunResult
from server import applications, jobs, questions
from server.agent_bridge import (SourceMap, build_agent_profile, cached_claude, make_form,
                                 no_claude)
from server.answer_bank import AnswerBank
from server.config import Config
from server.held_forms import FormSession, HeldForms
from server.store import Store, iso, new_id

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
STOP_TIMEOUT_SECONDS = 30.0
SITE_NAMES = {"greenhouse": "Greenhouse", "ashby": "Ashby", "lever": "Lever"}
MISSING_RESUME = "This form needs a resume. Add one on your Profile page."
HELD = "Filled and held for your review"
REUSED = "Still filled in its open window, and held for your review"
WINDOW_CLOSED = applications.WINDOW_CLOSED
WINDOW_CLOSED_READY = "You closed the form window; Submit will fill the form again first"


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
    pressed_submit: bool = False  # the run got as far as pressing Submit (submit runs only)
    session: FormSession | None = None  # the thread a fill ran on (it may hold the form)

    def field_by_label(self, label: str) -> FormField | None:
        wanted = normalize(label)
        return next((f for f in self.fields if normalize(f.label) == wanted), None)


@dataclass
class SubmitOutcome:
    """What `submit_run` did. `ctx` is None when the run couldn't even be prepared."""

    ctx: RunContext | None
    result: RunResult
    refilled: bool = False  # no held form, so the form was filled again before Submit

    @property
    def pressed(self) -> bool:
        """True if the run got as far as pressing Submit."""
        return self.ctx is not None and self.ctx.pressed_submit


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
        self._run_lock = threading.Lock()  # one browser run (fill or submit) at a time
        self._exclusive_waiting = 0  # submits waiting for the lock; the loop holds back meanwhile
        self._exclusive_guard = threading.Lock()
        self._active: set[str] = set()  # run ids in progress (fill or submit)
        self._cancelled: set[str] = set()  # run ids cancel_current() stopped
        self.forms = HeldForms()  # filled forms held open for review, by job id

    # ----- thread lifecycle -----

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._loop, name="agent-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the loop; a run in progress stops at its next field and goes back in line.

        Held windows are left alone: they go away with the process (Chromium is its child).
        """
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

    def held_form(self, job_id: str) -> FormSession | None:
        """The live session holding `job_id`'s filled window, if any."""
        return self.forms.get(job_id)

    def close_forms_for_tests(self) -> None:
        """Test teardown only: closes every held window so no Chromium outlives a test."""
        self.forms.close_all_for_tests()

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
        if self._stopping.is_set() or self._exclusive_waiting:  # a submit is waiting to go
            return None
        if not self._run_lock.acquire(blocking=False):  # pylint: disable=consider-using-with
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
                job_id = job["id"]
                session = self.forms.get(job_id)
                if session is not None and session.context is not None:
                    self._reuse_window(db, job, session)  # still open: no second window
                    return job_id
                jobs.reset_progress(job)
                job["question"] = None
                job["internal"]["question"] = None
                run_id = self.claim(job)
            self.run_job(job_id, run_id)
            return job_id
        finally:
            self._run_lock.release()

    def _reuse_window(self, db, job: dict, session: FormSession) -> None:
        """A queued job whose filled window is still open: back to `ready` on that window.

        A window that was already submitted and is waiting for its confirmation goes back to
        `handoff` instead (the form may have been sent).
        """
        job["internal"].update(runId=None, cancelRequested=False)
        if session.watching:
            self._to_handoff(db, job, self.watching_reason(job, session.submit_result))
            job["internal"]["windowWatched"] = True
            job["internal"]["askedForCode"] = bool(session.submit_result
                                                   and session.submit_result.asked_for_code)
            return
        jobs.reset_progress(job)
        self._to_ready(db, job, session.context, session.result, record_use=False,
                       event=REUSED)

    # ----- runs outside the loop (submit) -----

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Holds the run lock for a browser run outside the loop (POST /jobs/:id/submit).

        Waits for a fill in progress to end. While waiting, `run_next` starts nothing new, so a
        long queue can't keep the submit waiting. The loop is woken afterwards.
        """
        with self._exclusive_guard:
            self._exclusive_waiting += 1
        try:
            self._run_lock.acquire()  # pylint: disable=consider-using-with
        finally:
            with self._exclusive_guard:
                self._exclusive_waiting -= 1
        try:
            yield
        finally:
            self._run_lock.release()
            self.wake()

    def submit_run(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Submits a claimed `ready` job (spec 2.11, SUBMIT_REAL_FORM on).

        Presses Submit on the form held open since the fill. When there's none, or its window
        is gone, it fills the form again first (`outcome.refilled`), in a window held the same
        way. Never overlaps another browser run, and never closes the window unless the
        confirmation was seen and saved. The caller applies the outcome to the job.
        """
        with self.exclusive():
            try:
                session = self.forms.get(job_id)
                if session is not None:
                    outcome = self._submit_held(session, run_id)
                    if outcome is not None:
                        return outcome
                    log.info("The held form for job %s is gone; filling it again", job_id)
                return self._submit_again(job_id, run_id)
            finally:
                self._active.discard(run_id)
                self._cancelled.discard(run_id)

    def _submit_held(self, session: FormSession, run_id: str) -> SubmitOutcome | None:
        """Presses Submit on the held page. None when the page is gone (nothing was pressed)."""
        ctx = replace(session.context, run_id=run_id, pressed_submit=False, session=session)
        result = session.submit(
            on_event=lambda kind, **data: self._on_event(ctx, True, kind, data),
            should_stop=lambda: self.should_stop(ctx),
            should_abort=lambda: self._stopping.is_set() or run_id in self._cancelled,
            confirm_timeout_s=self.config.confirm_timeout_s)
        return None if result is None else SubmitOutcome(ctx, result)

    def _submit_again(self, job_id: str, run_id: str) -> SubmitOutcome:
        """Fills the form again (held, on its own thread), then presses Submit on it."""
        try:
            ctx = self.prepare(job_id, run_id)
        except KeyError:
            return SubmitOutcome(None, RunResult("cancelled", "The job is gone."), True)
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Couldn't prepare the submit for job %s", job_id)
            return SubmitOutcome(None, RunResult("failed", f"Couldn't start: {error}"), True)
        try:
            result = self.execute(ctx, submit=True)
        except Exception as error:  # pylint: disable=broad-except
            log.exception("Submit for job %s crashed", job_id)
            return SubmitOutcome(ctx, RunResult("failed", f"The agent crashed: {error}"), True)
        session = ctx.session
        if session is None or result.held is None:  # needs_input, failed or cancelled
            return SubmitOutcome(ctx, result, True)
        self.forms.hold(session)
        outcome = self._submit_held(session, run_id)
        if outcome is None:
            outcome = SubmitOutcome(ctx, RunResult("failed", "The new form window closed "
                                                             "before Submit."))
        outcome.refilled = True
        return outcome

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
        ask = cached_claude(self.store, job_id) if self.config.claude_enabled else no_claude
        answerer = Answerer(profile, ask, threshold=threshold)
        return RunContext(job_id, run_id, snapshot["company"], form, profile, answerer,
                          SourceMap.build(self.bank, ids))

    def execute(self, ctx: RunContext, submit: bool = False) -> RunResult:
        """Fills the form for `ctx` (never presses Submit). Events update the job while its run
        owns it.

        The fill runs on a new FormSession thread (`ctx.session`) that keeps the browser open if
        it ends `ready`; this thread only waits for the fill. With `submit=False` (a first fill)
        the job's `fields` are rebuilt as fields are filled. With `submit=True` (a submit that
        fills again first) only `phase` (submitting, confirming) and `currentField` change, so
        the fields shown at review time stay put.
        """
        try:
            ctx.fields = ctx.form.read_fields()
        except Exception:  # pylint: disable=broad-except
            ctx.fields = []  # ApplyRun reads them again and reports the error
        run = ApplyRun(
            ctx.answerer, self.store.dir("screenshots"), submit=False,
            show=self.config.show_browser, slow_mo=self.config.slow_mo_ms,
            on_event=lambda kind, **data: self._on_event(ctx, submit, kind, data),
            should_stop=lambda: self.should_stop(ctx), hold=True,
            confirm_timeout_s=self.config.confirm_timeout_s)
        self._active.add(ctx.run_id)
        try:
            ctx.session = FormSession(ctx.job_id, lambda: run.run(ctx.form, shot_name=ctx.job_id),
                                      context=ctx, on_confirmed=self._on_window_confirmed,
                                      on_window_closed=self._on_window_closed).start()
            return ctx.session.wait_filled()
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
    def owns(job: dict, run_id: str) -> bool:
        """True while `job` is running and still belongs to run `run_id`."""
        return AgentWorker._owns(job, run_id)

    @staticmethod
    def _owns(job: dict, run_id: str) -> bool:
        internal = job.get("internal") or {}
        return job.get("state") == "running" and internal.get("runId") == run_id \
            and not internal.get("cancelRequested")

    def _on_event(self, ctx: RunContext, submit: bool, kind: str, data: dict) -> None:
        if submit and kind == "phase" and data.get("name") == "submitting":
            ctx.pressed_submit = True  # emitted right before Submit is pressed
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
        session = ctx.session
        if session is not None and result.held is not None:
            # Held before the job shows `ready`, so a submit right away finds it. Kept even if
            # the job was cancelled or skipped meanwhile: applying again reuses the window.
            self.forms.hold(session)
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

    def to_question(self, db, job: dict, ctx: RunContext, result: RunResult) -> None:
        """`needs_input` on the run's first unanswered field (a submit whose answer went away)."""
        self._to_question(db, job, ctx, result)

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

    def _to_ready(self, db, job: dict, ctx: RunContext, result: RunResult,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                  record_use: bool = True, event: str = HELD) -> None:
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
            record = ctx.sources.record_for(label) if source == "saved" and record_use else None
            if record is not None:
                self.bank.record_use(record["id"], ctx.company, label)
        jobs.remove_from_queue(db, job["id"])
        jobs.add_event(job, "muted", event, now)

    # ----- held windows (called on their FormSession threads) -----

    def watching_reason(self, job: dict, result: RunResult | None) -> str:
        """Why a job is in `handoff` while its window waits for the confirmation."""
        return applications.watching_reason(job, self.config,
                                            bool(result and result.asked_for_code))

    def _on_window_confirmed(self, session: FormSession, result: RunResult) -> None:
        """A watched window shows the thank-you page (screenshot saved): record the application."""
        with self.store.tx() as db:
            job = jobs.find(db, session.job_id)
            if job is None or job.get("state") == "submitted":
                return  # wiped (DELETE /account) or already recorded
            applications.record_confirmed(self.store, db, job, result)
        log.info("Job %s: the confirmation showed up in its window; recorded", session.job_id)
        self.wake()

    def _on_window_closed(self, session: FormSession) -> None:
        """The person closed a held window: say so on the job, if it still matters."""
        with self.store.tx() as db:
            job = jobs.find(db, session.job_id)
            if job is None:
                return
            now = self.store.now_iso()
            if job.get("state") == "handoff" and session.watching:
                job["reason"] = WINDOW_CLOSED
                job["internal"]["windowWatched"] = False
                jobs.add_event(job, "amber", WINDOW_CLOSED, now)
            elif job.get("state") == "ready":
                jobs.add_event(job, "muted", WINDOW_CLOSED_READY, now)

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
