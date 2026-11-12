"""Setup and profile routes. WP1 has /preferences; WP2 adds resume, profile and common answers."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.store import Store, get_store

router = APIRouter()


class JobPreferencesBody(BaseModel):
    roleTypes: list[str]
    fullTime: bool
    internship: bool


@router.get("/preferences")
def get_preferences(store: Store = Depends(get_store)):
    return store.read("preferences")


@router.put("/preferences")
def put_preferences(body: JobPreferencesBody, store: Store = Depends(get_store)):
    """Stored only; the demo doesn't match jobs."""
    with store.tx() as db:
        db.preferences = body.model_dump()
        return dict(db.preferences)
