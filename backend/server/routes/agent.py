"""Agent routes: /settings, /agent/status, /agent/pause, /agent/resume, plus /health."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from server.config import Config, get_config
from server.errors import ApiError
from server.store import Db, Store, get_store, parse_iso

router = APIRouter()

SETTINGS_RANGES = {"confidenceThreshold": (0, 100), "dailyLimit": (1, 50)}


# ----- status (spec 2.10) -----

def sent_today(db: Db, now: datetime) -> int:
    """Applications the agent sent (dry runs included) whose submittedAt is today, local time."""
    today = now.astimezone().date()
    count = 0
    for app in db.applications:
        if app.get("submittedBy") != "agent":
            continue
        moment = parse_iso(app.get("submittedAt"))
        if moment and moment.astimezone().date() == today:
            count += 1
    return count


def queue_order(db: Db) -> list[str]:
    """Running ids, then queued ids in state.queue order, then waiting ids by approval time."""
    by_id = {job.get("id"): job for job in db.jobs}
    running = [job["id"] for job in db.jobs if job.get("state") == "running"]
    queued = [jid for jid in db.state.get("queue", [])
              if by_id.get(jid, {}).get("state") == "queued"]
    waiting = sorted((job for job in db.jobs if job.get("state") == "waiting"),
                     key=lambda job: job.get("approvedAt") or "")
    return running + queued + [job["id"] for job in waiting]


def agent_status(db: Db, now: datetime) -> dict:
    return {
        "paused": bool(db.state.get("paused")),
        "sentToday": sent_today(db, now),
        "dailyLimit": db.settings["dailyLimit"],
        "queue": queue_order(db),
    }


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
        # WP4: jobs.promote_waiting(db) goes here (a higher limit releases waiting jobs).
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
