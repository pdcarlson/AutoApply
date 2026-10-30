"""Figure out which ATS a job link belongs to (US5, F5).

We only support three applicant tracking systems for now. Anything else
gets rejected with a message instead of queued.
"""
from urllib.parse import urlparse

# host -> ats name
SUPPORTED_HOSTS = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}


def detect_ats(url: str) -> str | None:
    """Return 'greenhouse', 'lever' or 'ashby', or None if we don't support the site."""
    host = urlparse(url.strip()).netloc.lower()
    return SUPPORTED_HOSTS.get(host)


def company_from_url(url: str) -> str:
    """Best guess at the company from the link.

    All three sites put the company slug first in the path, e.g.
    https://jobs.lever.co/kestrelhealth/abc123 -> 'kestrelhealth'.
    """
    parts = [p for p in urlparse(url.strip()).path.split("/") if p]
    return parts[0] if parts else ""
