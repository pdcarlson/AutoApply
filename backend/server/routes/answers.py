"""Answer bank routes: GET/POST /answers, PATCH/DELETE /answers/:id (spec 2.5, section 3)."""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from server.answer_bank import ANSWER_CATEGORIES, AnswerBank
from server.errors import ApiError, not_found
from server.store import Store, get_store

router = APIRouter()


class AnswerInputBody(BaseModel):
    """AnswerInput. Loose types so a bad category or empty text gets `invalid_answer`."""
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    company: str | None = None


def get_bank(request: Request) -> AnswerBank:
    return request.app.state.answer_bank


def _invalid(message: str) -> ApiError:
    return ApiError(422, "invalid_answer", message)


def _validated(body: AnswerInputBody, partial: bool) -> dict:
    """The fields to write, trimmed. Raises 422 invalid_answer for a bad category or empty text."""
    sent = body.model_fields_set
    out: dict = {}
    if not partial or "category" in sent:
        if body.category not in ANSWER_CATEGORIES:
            raise _invalid(f"Pick a category: {', '.join(ANSWER_CATEGORIES)}.")
        out["category"] = body.category
    for key, what in (("question", "question"), ("answer", "answer")):
        if not partial or key in sent:
            value = (getattr(body, key) or "").strip()
            if not value:
                raise _invalid(f"The {what} can't be empty.")
            out[key] = value
    if not partial or "company" in sent:
        out["company"] = (body.company or "").strip() or None
    return out


def _added_source(store: Store) -> str:
    today = store.now().astimezone()  # the user's local day
    return f"You added it · {today:%b} {today.day}"


@router.get("/answers")
def list_answers(bank: AnswerBank = Depends(get_bank)):
    return bank.list()


@router.post("/answers", status_code=201)
def create_answer(body: AnswerInputBody, bank: AnswerBank = Depends(get_bank),
                  store: Store = Depends(get_store)):
    data = _validated(body, partial=False)
    return bank.create(data, origin="manual", source=_added_source(store))


@router.patch("/answers/{answer_id}")
def update_answer(answer_id: str, body: AnswerInputBody, bank: AnswerBank = Depends(get_bank)):
    patch = _validated(body, partial=True)
    answer = bank.update(answer_id, patch)
    if answer is None:
        raise not_found("Answer")
    return answer


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(answer_id: str, bank: AnswerBank = Depends(get_bank)):
    """Idempotent: 204 for an unknown id too."""
    bank.delete(answer_id)
    return Response(status_code=204)
