"""Agent question routes (spec 2.8): POST /jobs/:id/question/messages, PUT and DELETE
/jobs/:id/question/answer, POST /jobs/:id/question/accept.

Each answers 404 `not_found` when the job has no question. Accepting saves the answer to the
Answer bank under the form's exact label (so the re-run's lookup finds it), puts the job first
in the queue and wakes the worker; the re-run asks the next unanswered field, if any.
"""
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server import jobs, questions
from server.answer_bank import guess_category
from server.errors import ApiError, not_found
from server.store import Db, Store, get_store

router = APIRouter()

INVALID_OPTION = "Pick one of the options the form offers."


def _text(body: Any, key: str) -> str:
    value = body.get(key) if isinstance(body, dict) else None
    if not isinstance(value, str):
        raise ApiError(422, "invalid_request", f"Send {{\"{key}\": \"…\"}}.")
    return value


def _asking(db: Db, job_id: str) -> dict:
    """The job if it is waiting on a question, otherwise 404."""
    job = jobs.find(db, job_id)
    if job is None or not jobs.visible(job) or not job.get("question"):
        raise not_found("Question")
    return job


@router.post("/jobs/{job_id}/question/messages")
def reply(job_id: str, body: Any = Body(None), store: Store = Depends(get_store)):
    text = _text(body, "text").strip()
    if not text:
        raise ApiError(422, "invalid_request", "The reply can't be empty.")
    with store.tx() as db:
        job = _asking(db, job_id)
        question = questions.interpret(job["question"], job["internal"].get("question"), text)
        return deepcopy(question)


@router.put("/jobs/{job_id}/question/answer")
def pick(job_id: str, body: Any = Body(None), store: Store = Depends(get_store)):
    value = _text(body, "value")
    with store.tx() as db:
        job = _asking(db, job_id)
        if not questions.pickable(job["question"], job["internal"].get("question"), value):
            raise ApiError(422, "invalid_option", INVALID_OPTION)
        return deepcopy(questions.pick(job["question"], value))


@router.delete("/jobs/{job_id}/question/answer")
def revise(job_id: str, store: Store = Depends(get_store)):
    with store.tx() as db:
        return deepcopy(questions.revise(_asking(db, job_id)["question"]))


@router.post("/jobs/{job_id}/question/accept")
def accept(job_id: str, request: Request, body: Any = Body(None),
           store: Store = Depends(get_store)):
    scope = body.get("scope") if isinstance(body, dict) else None
    if scope not in ("all", "company"):
        raise ApiError(422, "invalid_request", 'scope must be "all" or "company".')
    bank = request.app.state.answer_bank
    with store.tx() as db:  # the bank shares the store's lock, so this is one step
        job = _asking(db, job_id)
        question = job["question"]
        proposed = question.get("proposedAnswer")
        if not proposed:
            raise ApiError(409, "no_answer", "There’s no answer to use yet.")
        internal = job["internal"].get("question") or {}
        label = internal.get("label") or question["field"]  # the form's exact label
        company = job.get("company") or ""
        today = store.now().astimezone()
        bank.upsert_by_question(
            label, proposed["value"], company if scope == "company" else None, origin="reply",
            source=f"You answered on {company}’s form · {today:%b} {today.day}",
            category=guess_category(label))
        job["question"] = None
        job["internal"]["question"] = None
        jobs.requeue_at_front(db, job)
        jobs.add_event(job, "accent", f"You answered “{label}”", store.now_iso())
        result = deepcopy(jobs.to_api_job(job))
    request.app.state.worker.wake()
    return result
