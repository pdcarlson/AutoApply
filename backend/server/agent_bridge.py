"""Builds the agent's form and its cached Claude helper from a server job record."""
import json

from agent.answers import claude as agent_claude
from agent.forms import form_for
from agent.forms.ashby_form import AshbyForm
from agent.forms.base_form import AtsForm
from agent.forms.form_field import FieldAnswer, FormField
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_board import AshbyBoard, GreenhouseBoard, JobBoard
from agent.jobs.job_link import JobLink
from server.config import BACKEND_DIR, Config
from server.store import Store

FAKE_FORMS = BACKEND_DIR / "agent" / "tests" / "fake_forms"
FAKE_COMPANY = "fakecompany"
# Only these exact test postings map to the local fake forms. Any other link, including
# fakecompany with another job id, is treated as a real posting.
FAKE_JOB_IDS = {
    "greenhouse": frozenset({"1001", "1002"}),
    "ashby": frozenset({"00000000-0000-4000-8000-000000001001"}),
}

# Looked up at call time, so tests can monkeypatch `server.agent_bridge.ask_claude`.
ask_claude = agent_claude.ask_claude


# ----- links and forms -----

def link_to_dict(link: JobLink) -> dict:
    """Return the JobLink as it is stored in a job's `internal.link`."""
    return {"url": link.url, "site": link.site, "company": link.company, "job_id": link.job_id,
            "pasted": link.pasted}


def link_of(job: dict) -> JobLink:
    """Return the JobLink stored on a job record."""
    return JobLink(**job["internal"]["link"])


def is_fake(link: JobLink, config: Config) -> bool:
    """Return True for the test postings that FAKE_GREENHOUSE routes to local fake forms."""
    return bool(config.fake_greenhouse) and link.company.lower() == FAKE_COMPANY \
        and link.job_id in FAKE_JOB_IDS.get(link.site, ())


def fake_job_data(site: str = "greenhouse") -> dict:
    """Return the saved API payload of the fake posting on `site`."""
    return json.loads((FAKE_FORMS / f"{site}_api.json").read_text(encoding="utf-8"))


def fake_boards() -> list[JobBoard]:
    """Return job boards that list the fake Greenhouse and Ashby postings, from local files."""
    ashby = fake_job_data("ashby")
    return [GreenhouseBoard(FAKE_COMPANY, data={"jobs": [fake_job_data("greenhouse")]}),
            AshbyBoard(FAKE_COMPANY, data={"jobs": [{**ashby, "location": ashby["locationName"]}]})]


def make_form(job: dict, config: Config) -> AtsForm:
    """Return the agent form for a job record (`internal.link`, `internal.jobData`).

    Raises UnsupportedLink for sites the agent can't fill. The fake postings never touch the
    network: their API payloads and pages are local files.
    """
    link = link_of(job)
    if is_fake(link, config):
        form_class = AshbyForm if link.site == "ashby" else GreenhouseForm
        return form_class(link, job_data=fake_job_data(link.site),
                          url=(FAKE_FORMS / f"{link.site}_form.html").resolve().as_uri())
    form = form_for(link)
    cached = (job.get("internal") or {}).get("jobData")
    if cached is not None:
        form.job_data = cached
    return form


# ----- Claude, cached per job -----

def cached_claude(store: Store, job_id: str):
    """Return an `ask_claude(field, facts)` that keeps Claude's guesses on the job.

    The guesses go in `internal.claudeCache`, so a run again after a question is free and gives
    the same answers. A "couldn't help" result (empty value, confidence 0: no API key, an API
    error) isn't kept, so adding a key later or a passing outage doesn't stick to the job.
    """
    def ask(form_field: FormField, facts: str) -> FieldAnswer:
        with store.tx() as db:
            hit = _claude_cache(db, job_id).get(form_field.key)
            if hit is not None:
                return FieldAnswer(hit.get("value", ""), "claude", int(hit.get("confidence", 0)),
                                   hit.get("reason", ""))
        guess = ask_claude(form_field, facts)  # outside the lock: this can take seconds
        if guess.value or guess.confidence:
            with store.tx() as db:
                job = next((job for job in db.jobs if job.get("id") == job_id), None)
                if job is not None:
                    job["internal"].setdefault("claudeCache", {})[form_field.key] = {
                        "value": guess.value, "confidence": guess.confidence,
                        "reason": guess.reason}
        return guess
    return ask


def no_claude(_form_field: FormField, _facts: str) -> FieldAnswer:
    """Never call Claude: for the quick answer check when a job is added, and Claude off."""
    return FieldAnswer("", "claude", 0, "Not asked.")


def _claude_cache(db, job_id: str) -> dict:
    """Return the job's saved Claude guesses by field key ({} when it has none)."""
    job = next((job for job in db.jobs if job.get("id") == job_id), None)
    return ((job or {}).get("internal") or {}).get("claudeCache", {})
