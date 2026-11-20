"""Setup and profile routes: the resume, profile, common answers and job preferences."""
from fastapi import APIRouter, Depends, File, Request, UploadFile

from server import common_answers
from server.accounts import Account, get_account, get_bank
from server.config import Config, get_config
from server.errors import ApiError, not_found
from server.resume.parse_job import ResumeParseJob
from server.resume.unplaced import accept_unplaced
from server.resume.upload import TYPE_MESSAGE, read_upload, resume_file, save_resume
from server.routes.auth import session_of
from server.routes.setup_bodies import (CommonAnswersBody, JobPreferencesBody, ProfileUpdateBody,
                                        UnplacedActionBody)
from server.store import Store, get_store, new_id
from server.store_docs import default_profile

router = APIRouter()


def public_profile(profile: dict) -> dict:
    """Return the API Profile: no server-only keys such as `_resumePath`.

    Experience saved before entries had a kind comes back as "work".
    """
    out = {key: value for key, value in profile.items() if not key.startswith("_")}
    if "experience" in out:
        out["experience"] = [{"kind": "work", **item} for item in out["experience"] or []]
    return out


def public_parse(parse: dict) -> dict:
    """Return the API ResumeParse: no `_parseId` or `_rawSections`."""
    return {key: value for key, value in parse.items() if not key.startswith("_")}


# ----- resume -----

@router.post("/resume", status_code=202)
def upload_resume(file: UploadFile | None = File(None), store: Store = Depends(get_store),
                  config: Config = Depends(get_config)):
    """Save the resume, start over with a fresh profile and start parsing in the background."""
    name, content = read_upload(file)
    with store.tx() as db:
        path, relative = save_resume(store, name, content)
        resume = resume_file(store, name, path, len(content))
        parse_id = new_id("parse")
        db.profile = {**default_profile(), "resume": resume, "_resumePath": relative}
        db.resume_parse = {"status": "parsing", "file": resume, "sections": [], "error": None,
                           "_parseId": parse_id}
        # A copy: the parse thread adds to `sections` while this response is still being sent.
        body = {**public_parse(db.resume_parse), "sections": []}
    ResumeParseJob(store, path, parse_id, config.resume_parse_step_ms, name).start()
    return body


@router.get("/resume/parse")
def get_resume_parse(store: Store = Depends(get_store)):
    """Return how the latest resume parse is going."""
    parse = store.read("resume_parse")
    if not parse:
        raise not_found("Resume")
    return public_parse(parse)


@router.put("/resume/file")
def replace_resume_file(file: UploadFile | None = File(None), store: Store = Depends(get_store)):
    """Swap the file without parsing it again; the profile fields stay as they are."""
    try:
        name, content = read_upload(file)
    except ApiError as error:
        if error.code == "invalid_type":
            raise ApiError(422, "invalid_type", TYPE_MESSAGE) from None
        raise
    with store.tx() as db:
        path, relative = save_resume(store, name, content)
        resume = resume_file(store, name, path, len(content))
        db.profile["resume"] = resume
        db.profile["_resumePath"] = relative
        return dict(resume)


# ----- profile -----

@router.get("/profile")
def get_profile(store: Store = Depends(get_store)):
    """Return the profile."""
    return public_profile(store.read("profile"))


@router.put("/profile")
def put_profile(body: ProfileUpdateBody, store: Store = Depends(get_store)):
    """Replace the editable fields sent; keep resume, unplaced and _resumePath."""
    sent = body.model_fields_set  # top-level keys only; nested items get their defaults
    update = {key: value for key, value in body.model_dump().items() if key in sent}
    with store.tx() as db:
        db.profile.update(update)
        return public_profile(db.profile)


@router.post("/profile/unplaced/{section_id}")
def resolve_unplaced(section_id: str, body: UnplacedActionBody,
                     store: Store = Depends(get_store)):
    """Accept or dismiss one unplaced resume section; either way it leaves the list."""
    with store.tx() as db:
        profile = db.profile
        unplaced = profile.get("unplaced") or []
        section = next((item for item in unplaced if item.get("id") == section_id), None)
        if section is None:
            raise not_found("Section")
        if body.action == "accept":
            accept_unplaced(profile, section)
        profile["unplaced"] = [item for item in unplaced if item.get("id") != section_id]
        return public_profile(profile)


@router.post("/profile/confirm")
def confirm_profile(account: Account = Depends(get_account)):
    """Mark the profile confirmed and return the session."""
    with account.store.tx() as db:
        db.state["profileConfirmed"] = True
        return session_of(db, account.user_id)


# ----- common answers -----

@router.get("/common-answers")
def get_common_answers(store: Store = Depends(get_store)):
    """Return setup's common answers."""
    return store.read("common_answers")


@router.put("/common-answers")
def put_common_answers(body: CommonAnswersBody, request: Request,
                       store: Store = Depends(get_store)):
    """Store the answers and mirror them into the Answer bank as `onb-*` records."""
    bank = get_bank(request)
    with store.tx() as db:
        db.common_answers = body.model_dump()
        if bank is not None:
            common_answers.sync_bank(bank, db.common_answers)
        return dict(db.common_answers)


# ----- preferences -----

@router.get("/preferences")
def get_preferences(store: Store = Depends(get_store)):
    """Return the job preferences."""
    return store.read("preferences")


@router.put("/preferences")
def put_preferences(body: JobPreferencesBody, store: Store = Depends(get_store)):
    """Store the job preferences; nothing matches jobs against them yet."""
    with store.tx() as db:
        db.preferences = body.model_dump()
        return dict(db.preferences)
