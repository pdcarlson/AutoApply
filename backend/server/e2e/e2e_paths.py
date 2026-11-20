"""Where the end-to-end check finds the repo, the resume and the two servers."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
FRONTEND = REPO / "frontend"
RESUME = BACKEND / "agent" / "applicant" / "example_resume.pdf"

API_PORT = 8080
WEB_PORT = 5173
API_HEALTH = f"http://127.0.0.1:{API_PORT}/api/health"
WEB_URL = f"http://localhost:{WEB_PORT}"
