"""Server configuration, read from the environment and backend/agent/.env.

`agent.settings` is imported first so it loads agent/.env; variables already set in the process
environment win over the file, which is how tests and scripts force values.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

import agent.settings as agent_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass
class Config:  # pylint: disable=too-many-instance-attributes
    """Everything the server reads from the environment, resolved once per app.

    Mutable on purpose: tests flip `submit_real_form` and friends on `app.state.config`.
    """
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8080
    submit_real_form: bool = False
    claude_enabled: bool = False
    profile_path: Path = agent_settings.PROFILE_PATH
    fake_greenhouse: bool = False
    show_browser: bool = False
    slow_mo_ms: int = 0
    resume_parse_step_ms: int = 300
    seed_bank_from_profile: bool = False
    # After Submit, how long to wait for the thank-you page (time to type an emailed code).
    confirm_timeout_s: int = 90
    # Filled forms kept open in their browser for the review; the oldest is closed past this.
    held_forms_max: int = 5


def load_config(data_dir: Path | str | None = None) -> Config:
    """Builds a Config from the current environment. `data_dir` overrides AUTOAPPLY_DATA_DIR."""
    if data_dir is None:
        data_dir = os.getenv("AUTOAPPLY_DATA_DIR") or DEFAULT_DATA_DIR
    return Config(
        data_dir=Path(data_dir).resolve(),
        host=os.getenv("AUTOAPPLY_HOST") or "127.0.0.1",
        port=_env_int("AUTOAPPLY_PORT", 8080),
        # The one switch for pressing Submit lives in agent/.env (or the environment).
        submit_real_form=agent_settings.SUBMIT_REAL_FORM,
        # USE_CLAUDE=false turns Claude off even when agent/.env has a key: Windows shells
        # can't set ANTHROPIC_API_KEY to an empty value (they delete it, and .env fills it in).
        claude_enabled=bool(os.getenv("ANTHROPIC_API_KEY")) and _env_bool("USE_CLAUDE", True),
        profile_path=Path(agent_settings.PROFILE_PATH),
        fake_greenhouse=_env_bool("FAKE_GREENHOUSE", False),
        show_browser=_env_bool("AGENT_SHOW_BROWSER", False),
        slow_mo_ms=_env_int("AGENT_SLOW_MO_MS", 0),
        resume_parse_step_ms=_env_int("RESUME_PARSE_STEP_MS", 300),
        seed_bank_from_profile=_env_bool("SEED_BANK_FROM_PROFILE", False),
        confirm_timeout_s=_env_int("CONFIRM_TIMEOUT_S", 90),
        held_forms_max=_env_int("HELD_FORMS_MAX", 5),
    )


def get_config(request: Request) -> Config:
    """FastAPI dependency: the app's Config."""
    return request.app.state.config
