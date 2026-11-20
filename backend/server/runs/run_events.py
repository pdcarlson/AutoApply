"""Shows a run's progress on its job as the agent reports it: phase, field, and what it filled."""
from server import jobs
from server.jobs import JobState
from server.live.live_views import LiveViews
from server.runs.form_session import FormSession
from server.runs.run_context import RunContext
from server.store import Store

# A submit that fills the form again first only shows these phases, so the fields shown at
# review time stay put.
SUBMIT_PHASES = ("submitting", "confirming")


def owns(job: dict, run_id: str) -> bool:
    """Return True while `job` is running and still belongs to run `run_id`."""
    internal = job.get("internal") or {}
    return job.get("state") == JobState.RUNNING and internal.get("runId") == run_id \
        and not internal.get("cancelRequested")


class RunEvents:
    """Writes the agent's run events onto the job, while the run still owns it."""

    def __init__(self, store: Store, live: LiveViews):
        self.store = store
        self.live = live

    def handle(self, ctx: RunContext, is_submit: bool, kind: str, data: dict) -> None:
        """Apply one event from ApplyRun (`browser`, `phase`, `field` or `filled`)."""
        if kind == "browser":
            self.live.set(ctx.job_id, ctx, data["page"])
            self._set_live_view(ctx.job_id, True)
            return
        if is_submit and kind == "phase" and data.get("name") == "submitting":
            ctx.pressed_submit = True  # sent right before Submit is pressed
        with self.store.tx() as db:
            job = jobs.find(db, ctx.job_id)
            if job is None or not owns(job, ctx.run_id):
                return
            if kind == "phase":
                if not is_submit or data["name"] in SUBMIT_PHASES:
                    job["phase"] = data["name"]
            elif kind == "field":
                job["currentField"] = data["label"]
            elif kind == "filled":
                job["currentField"] = None
                if not is_submit:
                    self._add_filled(job, ctx, data)

    def browser_closed(self, session: FormSession) -> None:
        """A run's thread ended, so its browser is closed: nothing to watch anymore."""
        if self.live.drop(session.job_id, session.context):
            self._set_live_view(session.job_id, False)

    @staticmethod
    def _add_filled(job: dict, ctx: RunContext, data: dict) -> None:
        """Add one filled field to the job and count it."""
        job.setdefault("fields", []).append(ctx.sources.filled_field(
            ctx.field_by_label(data["label"]), data["label"], data["value"], data["source"],
            data["confidence"]))
        job["progress"] = {**job["progress"], "filled": len(job["fields"])}

    def _set_live_view(self, job_id: str, is_live: bool) -> None:
        """Note on the job whether its browser is open to watch."""
        with self.store.tx() as db:
            job = jobs.find(db, job_id)
            if job is not None:
                job["internal"]["liveView"] = is_live
