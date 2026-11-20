"""The background job that reads an uploaded resume into the profile."""
import logging
import threading
import time
from pathlib import Path

from server.resume.mapper import sections_to_profile
from server.resume.resume_reader import read_resume
from server.store import Db, Store

log = logging.getLogger(__name__)


def unreadable(name: str) -> dict:
    """Return the ResumeParse error for a file with no text in it."""
    return {"code": "unreadable",
            "message": f"We couldn't read text from {name}. Fill your profile in by hand."}


class ResumeParseJob:
    """Parses one upload, reveals its labels one by one, then fills the profile.

    Every write first checks that `resume_parse._parseId` is still this job's id, so a newer
    upload or DELETE /account makes the job stop quietly.
    """

    def __init__(self, store: Store, path: Path | str, parse_id: str, step_ms: int = 0,
                 name: str | None = None):
        self.store = store
        self.path = Path(path)
        self.parse_id = parse_id
        self.step_ms = step_ms
        self.name = name or self.path.name  # the uploaded file's name

    def start(self) -> threading.Thread:
        """Run the job in a daemon thread and return that thread."""
        thread = threading.Thread(target=self.run, name="resume-parse", daemon=True)
        thread.start()
        return thread

    def run(self) -> None:
        """Parse the file and write the result, unless a newer upload has replaced it."""
        sections, result = self._parse()
        if result is None:
            with self.store.tx() as db:
                if self._is_current(db):
                    db.resume_parse.update(status="failed", error=unreadable(self.name))
            return
        patch, unplaced, labels = result
        for label in labels:
            if self.step_ms > 0:
                time.sleep(self.step_ms / 1000)
            with self.store.tx() as db:
                if not self._is_current(db):
                    return
                db.resume_parse["sections"].append(label)
        with self.store.tx() as db:
            if not self._is_current(db):
                return
            db.profile.update(patch)
            db.profile["unplaced"] = unplaced
            db.resume_parse.update(status="done", _rawSections=sections)

    def _parse(self) -> tuple[dict | None, tuple | None]:
        """Return (sections, sections_to_profile result), or (None, None) if it can't be read."""
        try:
            sections = read_resume(self.path)
            return sections, sections_to_profile(sections) if sections else None
        except Exception as error:  # pylint: disable=broad-except  # any bad file ends as "failed"
            log.warning("Resume parse failed for %s: %s", self.name, type(error).__name__)
            log.debug("Resume parse error", exc_info=True)
            return None, None

    def _is_current(self, db: Db) -> bool:
        """Return True while this job's upload is still the one being parsed."""
        parse = db.resume_parse
        return isinstance(parse, dict) and parse.get("_parseId") == self.parse_id
