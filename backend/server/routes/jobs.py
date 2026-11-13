"""Jobs (Inbox) routes: GET /jobs, GET /jobs/:id, POST /jobs, /jobs/apply, /jobs/cancel,
/jobs/:id/skip and /jobs/:id/restore (spec 2.9, 2.10).

/jobs/:id/submit and /jobs/:id/mark-submitted live in routes/applications.py, and the question
routes in routes/questions.py.
"""
import logging
import urllib.error
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from agent.answers.answerer import Answerer
from agent.jobs.job_link import JobLink, UnsupportedLink
from server import jobs
from server.agent_bridge import build_agent_profile, link_to_dict, make_form, no_claude
from server.config import Config, get_config
from server.errors import ApiError, not_found
from server.store import Store, get_store, new_id

log = logging.getLogger(__name__)

router = APIRouter()

ATS_BY_HOST = (("greenhouse.io", "Greenhouse"), ("ashbyhq.com", "Ashby"), ("lever.co", "Lever"))
FILLED_SITES = ("Greenhouse", "Lever")  # sites the agent reads and fills
INVALID_URL = "Copy the job’s full address from your browser, then paste it here."
CLOSED = "The company isn’t taking applications for it anymore."
FETCH_FAILED = "Couldn't load that posting from the site. Try again in a minute."


class AddJobBody(BaseModel):
    url: str


class JobIdsBody(BaseModel):
    jobIds: list[str]


def _title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _parse_link(url: str) -> tuple[JobLink, str]:
    """(agent JobLink, ats) or 422 invalid_url / unsupported_site (spec 2.9 steps 1-2)."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower() if parts.scheme in ("http", "https") else ""
    if not host:
        raise ApiError(422, "invalid_url", INVALID_URL)
    ats = next((name for suffix, name in ATS_BY_HOST if host.endswith(suffix)), None)
    if ats is None:
        raise ApiError(422, "unsupported_site",
                       f"Auto Apply adds jobs from Greenhouse, Ashby and Lever links. "
                       f"This one is from {host}.")
    try:
        return JobLink.parse(url), ats
    except UnsupportedLink as error:
        raise ApiError(422, "invalid_url", str(error)) from None


def _conflict(db, link: dict) -> dict | None:
    """The existing job if the posting is already known; raises 409 for applied or active."""
    wanted = jobs.link_key(link)
    for app in db.applications:
        try:
            app_link = link_to_dict(JobLink.parse(app.get("url") or ""))
        except UnsupportedLink:
            continue
        if jobs.link_key(app_link) == wanted:
            raise ApiError(409, "already_applied", "You already applied to this job.", {
                "code": "already_applied", "company": app.get("company", ""),
                "role": app.get("role", ""), "sentAt": app.get("submittedAt")})
    existing = jobs.find_by_link(db, link)
    if existing is not None and existing.get("state") not in jobs.HIDDEN_STATES:
        raise ApiError(409, "already_in_inbox", "That job is already in your Inbox.", {
            "code": "already_in_inbox", "company": existing.get("company", ""),
            "role": existing.get("role", ""), "jobId": existing["id"]})
    return existing


def _form_details(request: Request, link: JobLink, ats: str,  # pylint: disable=too-many-locals
                  config: Config) -> dict:
    """Reads a Greenhouse or Lever form (outside the lock) and works out its Inbox metadata."""
    store: Store = request.app.state.store
    probe = {"internal": {"link": link_to_dict(link), "jobData": None}}
    form = make_form(probe, config)
    try:
        fields = form.read_fields()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ApiError(422, "posting_closed", CLOSED) from None
        raise ApiError(502, "fetch_failed", FETCH_FAILED) from None
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("Couldn't read the %s form for %s", ats, link.url, exc_info=True)
        raise ApiError(502, "fetch_failed", FETCH_FAILED) from None
    data = form.job_data or {}

    profile, _ids = build_agent_profile(store, request.app.state.answer_bank,
                                        data.get("company_name") or _title(link.company))
    threshold = int(store.read("settings")["confidenceThreshold"])
    answerer = Answerer(profile, no_claude, threshold=threshold)
    to_ask = sum(1 for f in fields if f.required and answerer.answer(f) is None)

    checks = [{"status": "ok", "text": f"{ats} form · {_plural(len(fields), 'question')}"}]
    if to_ask:
        verb = "isn't" if to_ask == 1 else "aren't"
        checks.append({"status": "warn", "text": f"{_plural(to_ask, 'required question')} "
                                                 f"{verb} covered by your profile or Answer "
                                                 "bank yet"})
    return {
        "company": data.get("company_name") or _title(link.company),
        "role": data.get("title") or f"{ats} posting",
        "location": (data.get("location") or {}).get("name", "") or "",
        "formSummary": {"totalFields": len(fields), "fieldsToAsk": to_ask},
        "progress": {"filled": 0, "total": len(fields)},
        "checks": checks,
        "reason": (f"Asks {_plural(to_ask, 'question')} your profile doesn't cover"
                   if to_ask else "Added from a link"),
        "jobData": data,
    }


def _ashby_details(link: JobLink) -> dict:
    return {
        "company": _title(link.company),
        "role": "Ashby posting",
        "location": "",
        "formSummary": None,
        "progress": {"filled": 0, "total": 0},
        "checks": [{"status": "warn", "text": "AutoApply can't fill Ashby forms yet. "
                                              "You'll finish this one on the site."}],
        "reason": "Added from a link",
        "jobData": None,
    }


def _new_record(link: JobLink, ats: str, details: dict, now: str) -> dict:
    job_data = details.pop("jobData")
    return {
        "id": new_id("job"),
        "company": details["company"],
        "role": details["role"],
        "location": details["location"],
        "ats": ats,
        "url": link.url,
        "source": "added",
        "postedAt": None,
        "addedAt": now,
        "closesOn": None,
        "reason": details["reason"],
        "checks": details["checks"],
        "skipSuggested": False,
        "state": "open",
        "phase": None,
        "progress": details["progress"],
        "formSummary": details["formSummary"],
        "question": None,
        "readyAt": None,
        "fields": [],
        "currentField": None,
        "timeline": [{"kind": "muted", "text": "You added the link", "at": now}],
        "approvedAt": None,
        "internal": {
            "link": link_to_dict(link),
            "jobData": job_data,
            "claudeCache": {},
            "question": None,
            "questionCount": 0,
            "runId": None,
            "cancelRequested": False,
            "screenshot": None,
        },
    }


# ----- routes -----

@router.get("/jobs")
def list_jobs(store: Store = Depends(get_store)):
    with store.tx() as db:
        return [jobs.to_api_job(job) for job in db.jobs if jobs.visible(job)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, store: Store = Depends(get_store)):
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or not jobs.visible(job):
            raise not_found("Job")
        return jobs.to_api_job_detail(job)


@router.post("/jobs", status_code=201)
def add_job(body: AddJobBody, request: Request, store: Store = Depends(get_store),
            config: Config = Depends(get_config)):
    link, ats = _parse_link(body.url)
    with store.tx() as db:
        existing = _conflict(db, link_to_dict(link))
        if existing is not None:  # skipped earlier: adding it again restores it
            jobs.restore(existing)
            return jobs.to_api_job(existing)
    # Reading a real form is a network call: keep it outside the lock.
    details = _form_details(request, link, ats, config) if ats in FILLED_SITES \
        else _ashby_details(link)
    with store.tx() as db:
        existing = _conflict(db, link_to_dict(link))  # someone added it meanwhile
        if existing is not None:
            jobs.restore(existing)
            return jobs.to_api_job(existing)
        record = _new_record(link, ats, details, store.now_iso())
        db.jobs.append(record)
        return jobs.to_api_job(record)


@router.post("/jobs/apply")
def apply_jobs(body: JobIdsBody, request: Request, store: Store = Depends(get_store)):
    with store.tx() as db:
        if not db.state.get("profileConfirmed"):
            raise ApiError(409, "profile_not_confirmed", "Confirm your profile before applying.")
        queued, deferred = jobs.apply(db, body.jobIds, store.now())
    request.app.state.worker.wake()  # a job whose window is still open reuses it
    return {"queued": queued, "deferred": deferred}


@router.post("/jobs/cancel", status_code=204)
def cancel_jobs(body: JobIdsBody, request: Request, store: Store = Depends(get_store)):
    with store.tx() as db:
        jobs.cancel(db, body.jobIds)  # a filled window stays open; applying again reuses it
    request.app.state.worker.wake()
    return Response(status_code=204)


@router.post("/jobs/{job_id}/skip", status_code=204)
def skip_job(job_id: str, request: Request, store: Store = Depends(get_store)):
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or not jobs.visible(job):
            raise not_found("Job")
        jobs.skip(db, job)  # a filled window stays open (only the person closes it)
    request.app.state.worker.wake()
    return Response(status_code=204)


@router.post("/jobs/{job_id}/restore")
def restore_job(job_id: str, store: Store = Depends(get_store)):
    with store.tx() as db:
        job = jobs.find(db, job_id)
        if job is None or job.get("state") != "skipped":
            raise not_found("Job")
        jobs.restore(job)
        return jobs.to_api_job(job)
