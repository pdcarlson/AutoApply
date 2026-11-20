"""Agent routes: /settings, /agent/status, /agent/pause, /agent/resume, plus /health."""
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server.accounts import get_worker
from server.config import Config, get_config
from server.errors import ApiError
from server.job_queue import JobQueue
from server.store import Store, get_store

router = APIRouter()

SETTINGS_RANGES = {"confidenceThreshold": (0, 100), "dailyLimit": (1, 50)}


# ----- settings -----

def _invalid(message: str) -> ApiError:
    """Return the 422 for a bad settings change."""
    return ApiError(422, "invalid_settings", message)


def validate_settings_patch(patch: Any) -> dict:
    """Check a Partial<AgentSettings>; return only the known keys, as ints."""
    if not isinstance(patch, dict):
        raise _invalid("Settings must be a JSON object.")
    clean = {}
    for key, (low, high) in SETTINGS_RANGES.items():
        if key not in patch:
            continue
        value = patch[key]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise _invalid(f"{key} must be a whole number from {low} to {high}.")
        clean[key] = value
    return clean


@router.get("/settings")
def get_settings(store: Store = Depends(get_store)):
    """Return the agent settings."""
    return store.read("settings")


@router.patch("/settings")
def patch_settings(request: Request, patch: Any = Body(None), store: Store = Depends(get_store)):
    """Change some agent settings; return them all."""
    clean = validate_settings_patch(patch)
    with store.tx() as db:
        db.settings.update(clean)
        result = dict(db.settings)
        JobQueue(db, store.now()).promote_waiting()  # a higher limit releases waiting jobs
    get_worker(request).wake()
    return result


# ----- status, pause, resume -----

@router.get("/agent/status")
def get_status(store: Store = Depends(get_store)):
    """Return the AgentStatus: paused, sent today, the limit and the queue."""
    with store.tx() as db:
        return JobQueue(db, store.now()).status()


def _set_paused(request: Request, store: Store, is_paused: bool) -> dict:
    """Pause or resume the agent; return the AgentStatus."""
    with store.tx() as db:
        db.state["paused"] = is_paused
        status = JobQueue(db, store.now()).status()
    get_worker(request).wake()
    return status


@router.post("/agent/pause")
def pause(request: Request, store: Store = Depends(get_store)):
    """Stop the agent from starting new jobs."""
    return _set_paused(request, store, True)


@router.post("/agent/resume")
def resume(request: Request, store: Store = Depends(get_store)):
    """Let the agent start new jobs again."""
    return _set_paused(request, store, False)


# ----- health, for scripts -----

@router.get("/health")
def health(config: Config = Depends(get_config)):
    """Return that the server is up, and the switches it runs with."""
    return {
        "ok": True,
        "submitRealForm": config.submit_real_form,
        "fakeGreenhouse": config.fake_greenhouse,
        "claude": config.claude_enabled,
        "authMode": config.auth_mode,
    }
