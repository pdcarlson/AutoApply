"""Setup and profile routes (api.md "Setup and profile"; spec 2.5 and 2.12).

/resume, /resume/parse, /resume/file, /profile, /profile/unplaced/:id, /profile/confirm,
/common-answers and /preferences.
"""
import logging
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel

from server import common_answers, resume_import
from server.config import Config, get_config
from server.errors import ApiError, not_found
from server.konefal import page_count
from server.routes.auth import session_of
from server.store import Store, default_profile, get_store, new_id

log = logging.getLogger(__name__)

router = APIRouter()

MAX_RESUME_BYTES = 5 * 1024 * 1024
RESUME_DIR = "resume"
RESUME_TYPES = (".pdf", ".docx")
TYPE_MESSAGE = "Upload your resume as a PDF or DOCX."


# ----- bodies -----

class ProfileLinkBody(BaseModel):
    id: str
    label: str = ""
    url: str = ""
    fixed: bool = False


class CustomFieldBody(BaseModel):
    id: str
    label: str = ""
    value: str = ""


class EducationBody(BaseModel):
    id: str
    school: str = ""
    degreeType: str = ""
    major: str = ""
    gpa: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    coursework: str = ""


class ExperienceBody(BaseModel):
    id: str
    title: str = ""
    org: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    current: bool = False
    detail: str = ""


class ProjectBody(BaseModel):
    id: str
    name: str = ""
    tech: str = ""
    detail: str = ""


class ProfileUpdateBody(BaseModel):
    """ProfileUpdate: every Profile field but resume and unplaced. Only the keys sent change."""
    firstName: str = ""
    middleName: str = ""
    lastName: str = ""
    email: str = ""
    phone: str = ""
    street: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = ""
    links: list[ProfileLinkBody] = []
    education: list[EducationBody] = []
    experience: list[ExperienceBody] = []
    projects: list[ProjectBody] = []
    skills: list[str] = []
    custom: list[CustomFieldBody] = []


class UnplacedActionBody(BaseModel):
    action: Literal["accept", "dismiss"]


CommonQuestionKey = Literal["workAuthorized", "needsSponsorship", "graduation", "earliestStart",
                            "relocate", "locations", "expectedPay", "familyEmployers", "gender",
                            "hispanicLatino", "race", "veteran", "disability"]
Decline = Literal["decline"]


class CommonAnswersBody(BaseModel):
    workAuthorized: Literal["Yes", "No"] | None = None
    needsSponsorship: Literal["Yes", "No"] | None = None
    graduation: str | None = None
    earliestStart: str | None = None
    relocate: Literal["Yes", "No", "Depends"] | None = None
    locations: list[str] = []
    expectedPay: str = ""
    familyEmployers: list[str] = []
    # Voluntary self-ID (server/self_id.py): a value, "decline", or None when not answered yet
    gender: Literal["Male", "Female", "Non-binary"] | Decline | None = None
    hispanicLatino: Literal["Yes", "No"] | Decline | None = None
    race: Literal["American Indian or Alaska Native", "Asian", "Black or African American",
                  "Native Hawaiian or Other Pacific Islander", "White",
                  "Two or More Races"] | Decline | None = None
    veteran: Literal["Yes", "No"] | Decline | None = None
    disability: Literal["Yes", "No"] | Decline | None = None
    skipped: list[CommonQuestionKey] = []


class JobPreferencesBody(BaseModel):
    roleTypes: list[str]
    fullTime: bool
    internship: bool


# ----- helpers -----

def public_profile(profile: dict) -> dict:
    """The API Profile: drops server-only keys such as `_resumePath`."""
    return {k: v for k, v in profile.items() if not k.startswith("_")}


def public_parse(parse: dict) -> dict:
    """The API ResumeParse: drops `_parseId` and `_rawSections`."""
    return {k: v for k, v in parse.items() if not k.startswith("_")}


def _safe_name(name: str) -> str:
    """A file name safe to keep in data/resume/: no folders, no odd characters."""
    base = re.split(r"[\\/]", name or "")[-1].strip()
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .")
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = stem[:100] or "resume"
    return f"{stem}.{ext.lower()}" if ext else stem


def _read_upload(file: UploadFile | None) -> tuple[str, bytes]:
    """Validates an upload like the mock: (original name, bytes) or 422 invalid_type/too_large."""
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


def _save_resume(store: Store, name: str, content: bytes) -> tuple[Path, str]:
    """Replaces whatever is in data/resume/ with this file. Returns (path, relative path)."""
    folder = store.dir(RESUME_DIR)
    for old in folder.iterdir():
        if old.is_file():
            try:
                old.unlink()
            except OSError:
                log.warning("Couldn't remove the previous resume %s", old.name)
    safe = _safe_name(name)
    path = folder / safe
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(path)
    return path, f"{RESUME_DIR}/{safe}"


def _resume_file(store: Store, name: str, path: Path, size: int) -> dict:
    try:
        pages = page_count(path)
    except Exception:  # pylint: disable=broad-except
        pages = None
    return {"name": name, "sizeBytes": size, "pageCount": pages, "uploadedAt": store.now_iso()}


def _next_id(prefix: str, items: list[dict]) -> str:
    numbers = [int(m.group(1)) for item in items
               if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", str(item.get("id", ""))))]
    return f"{prefix}-{max(numbers, default=0) + 1}"


# ----- resume -----

@router.post("/resume", status_code=202)
def upload_resume(file: UploadFile | None = File(None), store: Store = Depends(get_store),
                  config: Config = Depends(get_config)):
    name, content = _read_upload(file)
    with store.tx() as db:
        path, relative = _save_resume(store, name, content)
        resume = _resume_file(store, name, path, len(content))
        parse_id = new_id("parse")
        db.profile = {**default_profile(), "resume": resume, "_resumePath": relative}
        db.resume_parse = {"status": "parsing", "file": resume, "sections": [], "error": None,
                           "_parseId": parse_id}
        body = public_parse(db.resume_parse)
    resume_import.start_parse(store, path, parse_id, config.resume_parse_step_ms, name)
    return body


@router.get("/resume/parse")
def get_resume_parse(store: Store = Depends(get_store)):
    parse = store.read("resume_parse")
    if not parse:
        raise not_found("Resume")
    return public_parse(parse)


@router.put("/resume/file")
def replace_resume_file(file: UploadFile | None = File(None), store: Store = Depends(get_store)):
    """Swaps the file without parsing it again; the profile fields stay as they are."""
    try:
        name, content = _read_upload(file)
    except ApiError as error:
        if error.code == "invalid_type":
            raise ApiError(422, "invalid_type", TYPE_MESSAGE) from None
        raise
    with store.tx() as db:
        path, relative = _save_resume(store, name, content)
        resume = _resume_file(store, name, path, len(content))
        db.profile["resume"] = resume
        db.profile["_resumePath"] = relative
        return dict(resume)


# ----- profile -----

@router.get("/profile")
def get_profile(store: Store = Depends(get_store)):
    return public_profile(store.read("profile"))


@router.put("/profile")
def put_profile(body: ProfileUpdateBody, store: Store = Depends(get_store)):
    """Replaces the editable fields sent; keeps resume, unplaced and _resumePath."""
    sent = body.model_fields_set  # top-level keys only; nested items get their defaults
    update = {k: v for k, v in body.model_dump().items() if k in sent}
    with store.tx() as db:
        db.profile.update(update)
        return public_profile(db.profile)


@router.post("/profile/unplaced/{section_id}")
def resolve_unplaced(section_id: str, body: UnplacedActionBody,
                     store: Store = Depends(get_store)):
    with store.tx() as db:
        profile = db.profile
        unplaced = profile.get("unplaced") or []
        section = next((s for s in unplaced if s.get("id") == section_id), None)
        if section is None:
            raise not_found("Section")
        if body.action == "accept":
            _accept_unplaced(profile, section)
        profile["unplaced"] = [s for s in unplaced if s.get("id") != section_id]
        return public_profile(profile)


def _accept_unplaced(profile: dict, section: dict) -> None:
    suggestion = section.get("suggestion")
    label, text = resume_import.split_label(section.get("text") or "")
    if suggestion == resume_import.COURSEWORK_SUGGESTION and profile.get("education"):
        school = profile["education"][0]
        school["coursework"] = ", ".join(filter(None, [(school.get("coursework") or "").strip(),
                                                       text.strip()]))
        return
    if suggestion in (resume_import.COURSEWORK_SUGGESTION, resume_import.CUSTOM_SUGGESTION):
        custom = profile.setdefault("custom", [])
        custom.append({"id": _next_id("cf", custom), "label": label or "From your resume",
                       "value": text})


@router.post("/profile/confirm")
def confirm_profile(store: Store = Depends(get_store)):
    with store.tx() as db:
        db.state["profileConfirmed"] = True
        return session_of(db)


# ----- common answers -----

@router.get("/common-answers")
def get_common_answers(store: Store = Depends(get_store)):
    return store.read("common_answers")


@router.put("/common-answers")
def put_common_answers(body: CommonAnswersBody, request: Request,
                       store: Store = Depends(get_store)):
    """Stores the answers and mirrors them into the Answer bank as `onb-*` records."""
    bank = request.app.state.answer_bank
    with store.tx() as db:
        db.common_answers = body.model_dump()
        if bank is not None:
            common_answers.sync_bank(bank, db.common_answers)
        return dict(db.common_answers)


# ----- preferences -----

@router.get("/preferences")
def get_preferences(store: Store = Depends(get_store)):
    return store.read("preferences")


@router.put("/preferences")
def put_preferences(body: JobPreferencesBody, store: Store = Depends(get_store)):
    """Stored only; the demo doesn't match jobs."""
    with store.tx() as db:
        db.preferences = body.model_dump()
        return dict(db.preferences)
