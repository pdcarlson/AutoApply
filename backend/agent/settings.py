"""Settings for the agent, read from agent/.env."""
import os
from pathlib import Path

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).parent
load_dotenv(AGENT_DIR / ".env")

# Until we trust it, the agent fills real forms but never presses Submit on them.
SUBMIT_REAL_FORM = os.getenv("SUBMIT_REAL_FORM", "false").lower() == "true"
PROFILE_PATH = AGENT_DIR / os.getenv("PROFILE_PATH", "applicant/example_profile.json")
# Slows the browser down (milliseconds per action) so you can follow it
SLOW_MO_MS = int(os.getenv("AGENT_SLOW_MO_MS") or 0)
RUNS_DIR = AGENT_DIR / "runs"

CLAUDE_MODEL = "claude-sonnet-5-5"
CONFIDENCE_THRESHOLD = 90
