"""Builds the agent's form and its cached Claude helper from a server job record."""
from agent.answers import claude as agent_claude
from agent.forms import form_for
from agent.forms.base_form import AtsForm
from agent.forms.form_field import FieldAnswer, FormField
from agent.jobs.job_link import JobLink
from server.store import Store

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


def make_form(job: dict) -> AtsForm:
    """Return the agent form for a job record (`internal.link`, `internal.jobData`).

    Raises UnsupportedLink for sites the agent can't fill.
    """
    form = form_for(link_of(job))
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
