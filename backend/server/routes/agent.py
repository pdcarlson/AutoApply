"""Agent routes: /settings, /agent/status, /agent/pause, /agent/resume, plus /health."""
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server import jobs
from server.config import Config, get_config
from server.errors import ApiError
from server.jobs import agent_status
from server.store import Store, get_store

router = APIRouter()

SETTINGS_RANGES = {"confidenceThreshold": (0, 100), "dailyLimit": (1, 50)}


# ----- settings -----

def _invalid(message: str) -> ApiError:
    return ApiError(422, "invalid_settings", message)


def validate_settings_patch(patch: Any) -> dict:
    """Checks a Partial<AgentSettings>; returns only the known keys, as ints."""
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
    return store.read("settings")


@router.patch("/settings")
def patch_settings(request: Request, patch: Any = Body(None), store: Store = Depends(get_store)):
    clean = validate_settings_patch(patch)
    with store.tx() as db:
        db.settings.update(clean)
        result = dict(db.settings)
        jobs.promote_waiting(db, store.now())  # a higher limit releases waiting jobs
    request.app.state.worker.wake()
    return result


# ----- status, pause, resume -----

@router.get("/agent/status")
def get_status(store: Store = Depends(get_store)):
    with store.tx() as db:
        return agent_status(db, store.now())


def _set_paused(request: Request, store: Store, paused: bool) -> dict:
    with store.tx() as db:
        db.state["paused"] = paused
        status = agent_status(db, store.now())
    request.app.state.worker.wake()
    return status


@router.post("/agent/pause")
def pause(request: Request, store: Store = Depends(get_store)):
    return _set_paused(request, store, True)


@router.post("/agent/resume")
def resume(request: Request, store: Store = Depends(get_store)):
    return _set_paused(request, store, False)


# ----- health (not in api.md; for scripts) -----

@router.get("/health")
def health(config: Config = Depends(get_config)):
    return {
        "ok": True,
        "submitRealForm": config.submit_real_form,
        "fakeGreenhouse": config.fake_greenhouse,
        "claude": config.claude_enabled,
    }
