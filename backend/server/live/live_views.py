"""Keeps track of which job has an open browser page, and opens a live stream of it."""
import logging
import threading

from agent.browser import PageAddress
from server.live.page_stream import BrowserGone, CdpPageStream, PageStream

log = logging.getLogger(__name__)


class LiveViews:
    """The open pages by job id, each with the owner (the run) that opened it. Thread-safe.

    `drop` only removes the entry of the owner that set it, so a run that ends late can't take
    away the browser of the run that replaced it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._views: dict[str, tuple[object, PageAddress]] = {}

    def set(self, job_id: str, owner: object, page: PageAddress) -> None:
        """Record that `owner` has `page` open for the job."""
        with self._lock:
            self._views[job_id] = (owner, page)

    def drop(self, job_id: str, owner: object) -> bool:
        """Remove `owner`'s entry for the job; return True if it was there."""
        with self._lock:
            entry = self._views.get(job_id)
            if entry is None or entry[0] is not owner:
                return False
            del self._views[job_id]
            return True

    def page(self, job_id: str) -> PageAddress | None:
        """Return where the job's open page is, or None."""
        with self._lock:
            entry = self._views.get(job_id)
            return entry[1] if entry else None

    async def open_stream(self, job_id: str) -> PageStream | None:
        """Return a stream of the job's browser, or None when it has none (or it is gone)."""
        page = self.page(job_id)
        if page is None:
            return None
        try:
            return await CdpPageStream.open(page)
        except BrowserGone as error:
            log.info("Job %s: no live view: %s", job_id, error)
            return None
