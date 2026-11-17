"""The postings collected from every company board, kept in a JSON file and refreshed regularly."""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.jobs.job_board import Posting, company_boards

log = logging.getLogger(__name__)

MAX_AGE = timedelta(hours=12)  # postings older than this are collected again
# For beta testing the feed keeps only the postings whose forms are the shortest, since a short
# form leaves the least to go wrong. Set KEEP to None to keep every posting.
KEEP = 50
CHECKED_PER_BOARD = 8  # how many of a board's newest postings have their form read
KEPT_PER_COMPANY = 3


class JobFeed:
    """Collects postings from the boards, saves them and hands them out."""

    def __init__(self, path, boards=None, keep=KEEP):
        self.path = Path(path)
        self.boards = company_boards() if boards is None else boards
        self.keep = keep
        self.postings = []
        self.fetched_at = None
        self.refreshing = False
        self.lock = threading.Lock()
        self.load()

    def load(self):
        """Read the postings saved by an earlier refresh, if there are any."""
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.postings = [Posting(**posting) for posting in saved["postings"]]
            self.fetched_at = datetime.fromisoformat(saved["fetched_at"])
        except (OSError, ValueError, KeyError, TypeError):
            self.postings, self.fetched_at = [], None

    def is_stale(self):
        """Return True if the postings were never collected or are older than MAX_AGE."""
        return self.fetched_at is None \
            or datetime.now(timezone.utc) - self.fetched_at > MAX_AGE

    def find(self, posting_id):
        """Return the posting with this id, or None."""
        for posting in self.postings:
            if posting.posting_id == posting_id:
                return posting
        return None

    def read_board(self, board):
        """Return one board's postings, or none if the site doesn't answer. With `keep` set,
        only its shortest forms come back, each paired with its number of questions."""
        try:
            postings = board.postings()
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Couldn't read the %s board for %s", board.site, board.company)
            return []
        return postings if self.keep is None else self.shortest_forms(board, postings)

    def shortest_forms(self, board, postings):
        """Return (required questions, posting) for the board's postings with the shortest
        forms, leaving out any whose form can't be read."""
        checked = []
        # Internships are checked first, since the testers are students
        internships_first = sorted(postings, key=lambda posting: not posting.internship)
        for posting in internships_first[:CHECKED_PER_BOARD]:
            try:
                checked.append((board.required_questions(board.read_form(posting)), posting))
            except (OSError, ValueError, KeyError, TypeError):
                log.warning("Couldn't read the form for %s", posting.url)
        checked.sort(key=lambda pair: pair[0])
        return checked[:KEPT_PER_COMPANY]

    def refresh(self):
        """Collect the postings from every board again and save them."""
        with ThreadPoolExecutor(max_workers=6) as pool:
            found = [posting for postings in pool.map(self.read_board, self.boards)
                     for posting in postings]
        if not found and self.postings:
            return  # every site failed (offline?), so keep what we have
        if self.keep is not None:
            found.sort(key=lambda pair: pair[0])
            found = [posting for _questions, posting in found[:self.keep]]
        self.postings = found
        self.fetched_at = datetime.now(timezone.utc)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "fetched_at": self.fetched_at.isoformat(),
            "postings": [asdict(posting) for posting in found]}), encoding="utf-8")

    def refresh_in_background(self):
        """Start a refresh on its own thread, unless one is already running."""
        with self.lock:
            if self.refreshing:
                return
            self.refreshing = True
        threading.Thread(target=self.refresh_then_finish, name="job-feed", daemon=True).start()

    def refresh_then_finish(self):
        """Run one refresh and mark it done, even if it fails."""
        try:
            self.refresh()
        finally:
            self.refreshing = False
