"""Adds a posting to the Inbox from its link: checks it, reads its form, and makes the job."""
import logging
import urllib.error
from urllib.parse import urlsplit

from agent.answers.answerer import Answerer
from agent.forms.base_form import PostingClosed
from agent.jobs.job_link import JobLink, UnsupportedLink
from server import jobs
from server.agent_bridge import link_to_dict, make_form, no_claude
from server.agent_profile import build_agent_profile
from server.answer_bank import AnswerBank
from server.errors import ApiError
from server.jobs import EventKind, JobState
from server.store import Db, Store, new_id

log = logging.getLogger(__name__)

ATS_BY_HOST = (("greenhouse.io", "Greenhouse"), ("ashbyhq.com", "Ashby"))
INVALID_URL = "Copy the job’s full address from your browser, then paste it here."
CLOSED = "The company isn’t taking applications for it anymore."
FETCH_FAILED = "Couldn't load that posting from the site. Try again in a minute."


class JobIntake:  # pylint: disable=too-few-public-methods  # one entry point: add
    """Turns pasted links and job board picks into Inbox jobs for one user."""

    def __init__(self, store: Store, bank: AnswerBank):
        self.store = store
        self.bank = bank

    def add(self, url: str, posted_at: str | None = None) -> dict:
        """Add the posting at `url` to the Inbox and return its record.

        A job skipped earlier is restored instead. `posted_at` is set for a posting picked
        from the job board. Raises the 422 and 409 errors of POST /jobs.
        """
        link, ats = _parse_link(url)
        with self.store.tx() as db:
            existing = _known_job(db, link_to_dict(link))
            if existing is not None:  # skipped earlier: adding it again restores it
                jobs.restore(existing)
                return existing
        # Reading a real form is a network call: keep it outside the lock.
        details = self._form_details(link, ats)
        with self.store.tx() as db:
            existing = _known_job(db, link_to_dict(link))  # someone added it meanwhile
            if existing is not None:
                jobs.restore(existing)
                return existing
            record = _new_record(link, ats, details, self.store.now_iso(), posted_at)
            db.jobs.append(record)
            return record

    def _form_details(self, link: JobLink, ats: str) -> dict:
        """Read the form and work out the Inbox details for it."""
        try:
            form = make_form({"internal": {"link": link_to_dict(link), "jobData": None}})
        except UnsupportedLink:
            return _handoff_details(link, ats)
        try:
            fields = form.read_fields()
        except PostingClosed:
            raise ApiError(422, "posting_closed", CLOSED) from None
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise ApiError(422, "posting_closed", CLOSED) from None
            raise ApiError(502, "fetch_failed", FETCH_FAILED) from None
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Couldn't read the %s form for %s", ats, link.url, exc_info=True)
            raise ApiError(502, "fetch_failed", FETCH_FAILED) from None
        posting = form.posting()
        company = posting["company"] or _title(link.company)
        to_ask = self._count_unanswered(fields, company)
        return {
            "company": company,
            "role": posting["title"] or f"{ats} posting",
            "location": posting["location"],
            "formSummary": {"totalFields": len(fields), "fieldsToAsk": to_ask},
            "progress": {"filled": 0, "total": len(fields)},
            "checks": _form_checks(ats, len(fields), to_ask),
            "reason": (f"Asks {_plural(to_ask, 'question')} your profile doesn't cover"
                       if to_ask else "Added from a link"),
            "jobData": form.job_data,
        }

    def _count_unanswered(self, fields: list, company: str) -> int:
        """Return how many required fields the profile and Answer bank don't answer yet."""
        profile, _ids = build_agent_profile(self.store, self.bank, company)
        threshold = int(self.store.read("settings")["confidenceThreshold"])
        answerer = Answerer(profile, no_claude, threshold=threshold)
        return sum(1 for form_field in fields
                   if form_field.required and answerer.answer(form_field) is None)


def _title(slug: str) -> str:
    """Return a board slug like "fake-company" as "Fake Company"."""
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def _plural(count: int, word: str) -> str:
    """Return "1 question" or "3 questions"."""
    return f"{count} {word}" + ("" if count == 1 else "s")


def _parse_link(url: str) -> tuple[JobLink, str]:
    """Return (agent JobLink, ats name), or raise 422 invalid_url or unsupported_site."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower() if parts.scheme in ("http", "https") else ""
    if not host:
        raise ApiError(422, "invalid_url", INVALID_URL)
    ats = next((name for suffix, name in ATS_BY_HOST if host.endswith(suffix)), None)
    if ats is None:
        raise ApiError(422, "unsupported_site",
                       f"Auto Apply adds jobs from Greenhouse and Ashby links. "
                       f"This one is from {host}.")
    try:
        return JobLink.parse(url), ats
    except UnsupportedLink as error:
        raise ApiError(422, "invalid_url", str(error)) from None


def _known_job(db: Db, link: dict) -> dict | None:
    """Return the skipped job for this posting; raise 409 if it was applied to or is active."""
    wanted = jobs.link_key(link)
    for application in db.applications:
        try:
            application_link = link_to_dict(JobLink.parse(application.get("url") or ""))
        except UnsupportedLink:
            continue
        if jobs.link_key(application_link) == wanted:
            raise ApiError(409, "already_applied", "You already applied to this job.", {
                "code": "already_applied", "company": application.get("company", ""),
                "role": application.get("role", ""), "sentAt": application.get("submittedAt")})
    existing = jobs.find_by_link(db, link)
    if existing is not None and jobs.visible(existing):
        raise ApiError(409, "already_in_inbox", "That job is already in your Inbox.", {
            "code": "already_in_inbox", "company": existing.get("company", ""),
            "role": existing.get("role", ""), "jobId": existing["id"]})
    return existing


def _form_checks(ats: str, field_count: int, to_ask: int) -> list[dict]:
    """Return the Inbox checks for a form that was read."""
    checks = [{"status": "ok", "text": f"{ats} form · {_plural(field_count, 'question')}"}]
    if to_ask:
        verb = "isn't" if to_ask == 1 else "aren't"
        checks.append({"status": "warn", "text": f"{_plural(to_ask, 'required question')} "
                                                 f"{verb} covered by your profile or Answer "
                                                 "bank yet"})
    return checks


def _handoff_details(link: JobLink, ats: str) -> dict:
    """Return the Inbox details for a site the agent can't fill: the person finishes it."""
    return {
        "company": _title(link.company),
        "role": f"{ats} posting",
        "location": "",
        "formSummary": None,
        "progress": {"filled": 0, "total": 0},
        "checks": [{"status": "warn", "text": f"AutoApply can't fill {ats} forms yet. "
                                              "You'll finish this one on the site."}],
        "reason": "Added from a link",
        "jobData": None,
    }


def _new_record(link: JobLink, ats: str, details: dict, now: str,
                posted_at: str | None) -> dict:
    """Return a new Inbox job record; `posted_at` is set for a posting from the job board."""
    is_matched = posted_at is not None
    return {
        "id": new_id("job"), "company": details["company"], "role": details["role"],
        "location": details["location"], "ats": ats, "url": link.url,
        "source": "matched" if is_matched else "added", "postedAt": posted_at,
        "addedAt": now, "closesOn": None, "reason": details["reason"],
        "checks": details["checks"], "skipSuggested": False, "state": JobState.OPEN,
        "phase": None, "progress": details["progress"], "formSummary": details["formSummary"],
        "question": None, "readyAt": None,
        "fields": [],  # what the agent filled or plans to fill
        "currentField": None,  # the label being filled right now
        "timeline": [{"kind": EventKind.MUTED, "at": now,  # kept for the Application
                      "text": "You picked it from Jobs" if is_matched else "You added the link"}],
        "approvedAt": None,  # when Apply was pressed: orders the `waiting` jobs
        # Server-only, never sent. Runs later add windowWatched (a watched window after an
        # unconfirmed Submit), askedForCode (that window wants an emailed code) and liveView
        # (the browser is open to watch); restarts clear all three.
        "internal": {
            "link": link_to_dict(link),
            "jobData": details["jobData"],  # the posting's API payload, read when added
            "claudeCache": {},  # Claude's guesses by field key, so runs again are free
            "question": None,  # the field the current question asks about
            "questionCount": 0,  # how many questions were asked (ids q-<jobId>-<n>)
            "runId": None,  # the run that owns the job while it is `running`
            "cancelRequested": False,  # the run stops at the next field
            "screenshot": None,  # <id>-filled.png from the last fill that reached `ready`
        },
    }
