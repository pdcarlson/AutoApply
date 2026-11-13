"""What the browser extension needs to fill a job's form in the person's own browser.

Some sites turn applications from the agent's browser away (server.applications.BLOCKED). The
extension (extension/ at the repo root) fills the same answers into the form in the person's own
browser instead, where they review it, press Submit and do any CAPTCHA themselves.

- `plan(...)` is the answers for the job a page link points at: what the agent filled or planned
  for it, topped up from the profile, setup answers and Answer bank. Claude is never called here.
  Protected fields (CAPTCHA, sign-in, password, SSN) are named but never given a value.
- `resume_file(...)` is the resume to attach.
- `submitted(...)` records the application once the site's thank-you page shows.
"""
from pathlib import Path

from agent.answers.answerer import Answerer
from agent.applicant.profile import normalize
from agent.forms.protected import ProtectedFieldDetector
from agent.jobs.job_link import JobLink, UnsupportedLink
from server import applications, jobs
from server.agent_bridge import build_agent_profile, link_to_dict, make_form, no_claude
from server.errors import ApiError, not_found
from server.store import Store

NOT_A_JOB = "That page isn't a Greenhouse, Lever or Ashby job."
NOT_IN_INBOX = "That job isn't in your Inbox. Paste its link into AutoApply first."
CANT_FILL = "AutoApply can't fill that site's forms yet."
NO_RESUME = "There's no resume on your profile."
BUSY = "The agent is working on this job right now. Try again when it's done."
IN_BROWSER = "You're finishing this one in your own browser"


def _job_for(db, url: str) -> dict:
    """The Inbox job a page link points at, or 422/404."""
    try:
        link = JobLink.parse(url or "")
    except UnsupportedLink:
        raise ApiError(422, "invalid_url", NOT_A_JOB) from None
    job = jobs.find_by_link(db, link_to_dict(link))
    if job is None or not jobs.visible(job):
        raise ApiError(404, "not_in_inbox", NOT_IN_INBOX)
    return job


def plan(store: Store, bank, config, url: str) -> dict:
    """The fill plan for the job at `url`: one entry per form field the agent has a value for."""
    with store.tx() as db:
        job = _job_for(db, url)
        snapshot = {"id": job["id"], "company": job.get("company", ""),
                    "role": job.get("role", ""), "ats": job.get("ats"),
                    "internal": dict(job["internal"]),
                    "filled": {normalize(f["label"]): f["value"]
                               for f in job.get("fields") or []}}
        threshold = int(db.settings["confidenceThreshold"])
    try:
        form = make_form(snapshot, config)
        fields = form.read_fields()
    except UnsupportedLink:
        raise ApiError(409, "unsupported_site", CANT_FILL) from None
    profile, _ids = build_agent_profile(store, bank, snapshot["company"])
    answerer = Answerer(profile, no_claude, threshold=threshold)
    detector = ProtectedFieldDetector()

    filled, unanswered, protected, resume = [], [], [], None
    for form_field in fields:
        if detector.check_question(form_field):
            protected.append(form_field.label)
            continue
        if form_field.kind == "file":
            if form_field.profile_key == "resume_path" and profile.resume_path:
                resume = {"key": form_field.key, "name": Path(profile.resume_path).name,
                          "url": f"/api/extension/jobs/{snapshot['id']}/resume"}
            elif form_field.required:
                unanswered.append(form_field.label)
            continue
        # Today's profile and Answer bank first, so a value changed since the agent's fill
        # (an email, say) isn't brought back; what the agent filled covers the rest.
        answer = answerer.answer(form_field)
        value = (answer.value if answer else "") \
            or snapshot["filled"].get(normalize(form_field.label), "")
        if value:
            filled.append({"key": form_field.key, "label": form_field.label,
                           "kind": form_field.kind, "value": value})
        elif form_field.required:
            unanswered.append(form_field.label)
    return {"jobId": snapshot["id"], "company": snapshot["company"], "role": snapshot["role"],
            "ats": snapshot["ats"], "fields": filled, "resume": resume,
            "unanswered": unanswered, "protected": protected}


def resume_file(store: Store, bank, job_id: str) -> Path:
    """The resume on the profile, for the extension to attach. 404 without one."""
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None:
            raise not_found("Job")
        company = job.get("company", "")
    profile, _ids = build_agent_profile(store, bank, company)
    if not profile.resume_path:
        raise ApiError(404, "no_resume", NO_RESUME)
    return Path(profile.resume_path)


def submitted(store: Store, worker, job_id: str) -> dict:
    """The person submitted the job in their own browser (its thank-you page showed); returns
    the API `Application`. Works from any state the job can wait in, not only `handoff`."""
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None:
            raise not_found("Job")
        if job.get("state") == "running":
            raise ApiError(409, "job_running", BUSY)
        if job.get("state") not in ("handoff", "submitted"):
            job.update(state="handoff", phase=None, currentField=None, question=None,
                       reason=IN_BROWSER)
            job["internal"]["question"] = None
            jobs.remove_from_queue(db, job_id)
    return applications.mark_submitted(store, worker, job_id)
