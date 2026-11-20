"""What one run of one job carries along, and what a submit run did."""
from dataclasses import dataclass, field

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile, normalize
from agent.forms.base_form import AtsForm
from agent.forms.form_field import FormField
from agent.runner.apply_run import RunResult
from server.answer_sources import SourceMap
from server.runs.form_session import FormSession


@dataclass
class RunContext:  # pylint: disable=too-many-instance-attributes  # one run's whole setup
    """Everything one run of one job needs, built by `AgentWorker.prepare`."""

    job_id: str
    run_id: str
    company: str
    form: AtsForm
    profile: Profile
    answerer: Answerer
    sources: SourceMap
    fields: list[FormField] = field(default_factory=list)  # filled in after read_fields
    pressed_submit: bool = False  # the run got as far as pressing Submit (submit runs only)
    session: FormSession | None = None  # the thread a fill ran on (it may hold the form)

    def field_by_label(self, label: str) -> FormField | None:
        """Return the form's field with this label, or None."""
        wanted = normalize(label)
        return next((form_field for form_field in self.fields
                     if normalize(form_field.label) == wanted), None)

    def filled_fields(self, result: RunResult) -> list[dict]:
        """Return the API FilledFields for everything the run filled."""
        return [self.sources.filled_field(self.field_by_label(label), label, value, source,
                                          confidence)
                for label, value, source, confidence in result.filled_detail]


@dataclass
class SubmitOutcome:
    """What `AgentWorker.submit_run` did; `ctx` is None when the run couldn't be prepared."""

    ctx: RunContext | None
    result: RunResult
    refilled: bool = False  # no held form, so the form was filled again before Submit

    @property
    def pressed(self) -> bool:
        """Return True if the run got as far as pressing Submit."""
        return self.ctx is not None and self.ctx.pressed_submit
