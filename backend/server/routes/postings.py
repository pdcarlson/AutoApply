"""Job board routes: GET /postings and POST /postings/:id/apply (US14, US15).

The postings come from `app.state.job_feed` (agent.jobs.job_feed), which collects them from the
company boards and collects them again when they get old. Each request ranks them against the
profile as it is now, so nothing about the ranking is saved.
"""
from fastapi import APIRouter, Depends, Request

from agent.jobs.fit_ranker import FitRanker
from agent.jobs.job_board import Posting
from server import jobs
from server.config import Config, get_config
from server.errors import ApiError, not_found
from server.routes.jobs import add_from_link
from server.store import Store, get_store, iso

router = APIRouter()

ATS_NAMES = {"greenhouse": "Greenhouse", "ashby": "Ashby"}


def _ranker(store: Store) -> FitRanker:
    """A FitRanker for the profile, common answers and preferences as they are now."""
    profile, common = store.read("profile"), store.read("common_answers")
    preferences = store.read("preferences")
    today = iso(store.now())[:10]
    in_school = any((item.get("end") or "") > today for item in profile["education"])
    skills = list(profile["skills"])
    for project in profile["projects"]:
        skills += [tech.strip() for tech in (project.get("tech") or "").split(",")]
    # Without chosen role types, the jobs they've had and what they study say what fits.
    interests = preferences["roleTypes"] or (
        [item.get("title") or "" for item in profile["experience"]
         if (item.get("kind") or "work") == "work"]
        + [item.get("major") or "" for item in profile["education"]])
    return FitRanker(skills=skills, interests=interests,
                     places=[*common["locations"], profile["city"]],
                     wants_internship=preferences["internship"] or in_school,
                     wants_full_time=preferences["fullTime"])


def _placed(db) -> dict[tuple, dict]:
    """link key -> the job record, for every posting already in the Inbox or applied to."""
    return {jobs.link_key(job["internal"]["link"]): job for job in db.jobs
            if job.get("state") != "skipped"}


def _to_api_posting(posting: Posting, fit, placed: dict) -> dict:
    job = placed.get((posting.site, posting.board.lower(), posting.job_id))
    status = "open" if job is None else "applied" if job["state"] == "submitted" else "in_inbox"
    return {
        "id": posting.posting_id,
        "company": posting.company,
        "role": posting.title,
        "location": posting.location,
        "ats": ATS_NAMES[posting.site],
        "url": posting.url,
        "postedAt": posting.posted_at or None,
        "internship": posting.internship,
        "fit": {"score": fit.score, "reasons": fit.reasons},
        "status": status,
        "jobId": job["id"] if status == "in_inbox" else None,
    }


@router.get("/postings")
def list_postings(request: Request, store: Store = Depends(get_store)):
    """The best-fitting postings, best first. `refreshing` is true while they're collected."""
    feed = request.app.state.job_feed
    if feed.is_stale():
        feed.refresh_in_background()
    ranked = _ranker(store).rank(feed.postings)
    with store.tx() as db:
        placed = _placed(db)
    return {
        "postings": [_to_api_posting(posting, fit, placed) for fit, posting in ranked],
        "fetchedAt": iso(feed.fetched_at) if feed.fetched_at else None,
        "refreshing": feed.refreshing,
    }


@router.post("/postings/{posting_id}/apply")
def apply_to_posting(posting_id: str, request: Request, store: Store = Depends(get_store),
                     config: Config = Depends(get_config)):
    """Adds the posting to the Inbox and starts its application, like a pasted link (UC2)."""
    posting = request.app.state.job_feed.find(posting_id)
    if posting is None:
        raise not_found("Posting")
    if not store.read("state").get("profileConfirmed"):
        raise ApiError(409, "profile_not_confirmed", "Confirm your profile before applying.")
    record = add_from_link(posting.url, request, store, config,
                           posted_at=posting.posted_at or store.now_iso())
    with store.tx() as db:
        _queued, deferred = jobs.apply(db, [record["id"]], store.now())
        job = jobs.to_api_job(jobs.find(db, record["id"]))
    request.app.state.worker.wake()
    return {"job": job, "deferred": bool(deferred)}
