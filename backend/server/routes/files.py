"""Static files from the data dir: GET /screenshots/{name} (not in api.md; feeds screenshotUrl)."""
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from server.errors import not_found
from server.store import Store, get_store

router = APIRouter()

SCREENSHOT_NAME = re.compile(r"^[A-Za-z0-9_-]+\.png$")


def screenshot_url(name: str) -> str:
    """The `screenshotUrl` for a file in data/screenshots/."""
    return f"/api/screenshots/{name}"


@router.get("/screenshots/{name}")
def get_screenshot(name: str, store: Store = Depends(get_store)):
    if not SCREENSHOT_NAME.match(name):
        raise not_found("Screenshot")
    path = store.path("screenshots", name)
    if not path.is_file():
        raise not_found("Screenshot")
    return FileResponse(path, media_type="image/png")
