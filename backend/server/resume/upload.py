"""Checks an uploaded resume file and keeps it in the data folder."""
import logging
import re
from pathlib import Path

from fastapi import UploadFile

from server.autoapply_modules import page_count
from server.errors import ApiError
from server.store import Store

log = logging.getLogger(__name__)

MAX_RESUME_BYTES = 5 * 1024 * 1024
RESUME_DIR = "resume"
RESUME_TYPES = (".pdf", ".docx")
TYPE_MESSAGE = "Upload your resume as a PDF or DOCX."


def read_upload(file: UploadFile | None) -> tuple[str, bytes]:
    """Return the upload's (original name, bytes); raise 422 invalid_type or too_large."""
    if file is None or not getattr(file, "filename", None):
        raise ApiError(422, "invalid_type", TYPE_MESSAGE)
    name = file.filename
    if not name.lower().endswith(RESUME_TYPES):
        raise ApiError(422, "invalid_type",
                       f"{name} isn’t a PDF or DOCX. Upload your resume as a PDF or DOCX.")
    content = file.file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise ApiError(422, "too_large", f"{name} is over the 5 MB limit.")
    return name, content


def save_resume(store: Store, name: str, content: bytes) -> tuple[Path, str]:
    """Replace whatever is in data/resume/ with this file; return (path, relative path)."""
    folder = store.dir(RESUME_DIR)
    for old in folder.iterdir():
        if old.is_file():
            try:
                old.unlink()
            except OSError:
                log.warning("Couldn't remove the previous resume %s", old.name)
    safe = _safe_name(name)
    path = folder / safe
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path, f"{RESUME_DIR}/{safe}"


def resume_file(store: Store, name: str, path: Path, size: int) -> dict:
    """Return the API ResumeFile for a saved upload."""
    try:
        pages = page_count(path)
    except Exception:  # pylint: disable=broad-except  # a file it can't count still uploads
        pages = None
    return {"name": name, "sizeBytes": size, "pageCount": pages, "uploadedAt": store.now_iso()}


def _safe_name(name: str) -> str:
    """Return a file name safe to keep in data/resume/: no folders, no odd characters."""
    base = re.split(r"[\\/]", name or "")[-1].strip()
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .")
    stem, dot, extension = base.rpartition(".")
    if not dot:
        stem, extension = base, ""
    stem = stem[:100] or "resume"
    return f"{stem}.{extension.lower()}" if extension else stem
