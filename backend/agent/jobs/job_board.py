"""Reads the open postings on a company's public job board. One board class per site."""
import html
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.request import Request, urlopen

from agent.forms import ashby_form, greenhouse_form
from agent.forms.ashby_form import USER_AGENT

# Company job boards the feed pulls from, by the name each site uses in its links
COMPANY_BOARDS = {
    "greenhouse": ["airbnb", "coinbase", "datadog", "discord", "duolingo", "figma", "instacart",
                   "lyft", "mongodb", "pinterest", "reddit", "robinhood", "roblox", "samsara",
                   "twitch", "verkada"],
    # Only companies whose application page is on jobs.ashbyhq.com: some (Cursor) list their
    # jobs through Ashby but take applications on their own site, which the agent can't fill
    "ashby": ["cohere", "docker", "elevenlabs", "linear", "notion", "perplexity",
              "plaid", "ramp", "replit", "sentry", "skydio", "snowflake", "supabase", "vanta"],
}
MAX_PER_BOARD = 150  # the newest postings kept from one board, so no company fills the feed
TEXT_LIMIT = 3000    # how much of a description is kept to look for skills in
INTERNSHIP = re.compile(r"\bintern(ship)?s?\b|\bco-?op\b", re.IGNORECASE)


@dataclass
class Posting:  # pylint: disable=too-many-instance-attributes
    """One open job, in the same shape whichever site it came from."""

    site: str
    board: str  # the company's name in the site's links
    job_id: str
    company: str
    title: str
    url: str
    location: str = ""
    department: str = ""
    internship: bool = False
    posted_at: str = ""
    text: str = ""  # the description as plain text

    @property
    def posting_id(self):
        """Return an id that stays the same each time the board is read."""
        return f"{self.site}-{self.board}-{self.job_id}"


def plain_text(markup):
    """Return a description without its HTML tags, cut to TEXT_LIMIT."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(markup or ""))
    return re.sub(r"\s+", " ", text).strip()[:TEXT_LIMIT]


class JobBoard(ABC):
    """One company's job board on one applicant tracking system."""

    site = ""

    def __init__(self, company, data=None):
        self.company = company
        # Tests pass in saved API data instead of going online
        self.data = data

    @abstractmethod
    def api_url(self):
        """Return the address of the site's public list of this company's postings."""

    @abstractmethod
    def to_posting(self, job):
        """Turn one job from the site's API into a Posting."""

    @abstractmethod
    def read_form(self, posting):
        """Return the site's data for one posting's application form."""

    @abstractmethod
    def required_questions(self, form):
        """Return how many required questions an application form asks."""

    def read_json(self, url):
        """Return what the site's API answers at this address."""
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def is_listed(self, job):  # pylint: disable=unused-argument
        """Return False for a job the company keeps off its public board."""
        return True

    def postings(self):
        """Return the board's newest postings, newest first."""
        if self.data is None:
            self.data = self.read_json(self.api_url())
        found = [self.to_posting(job) for job in self.data.get("jobs") or []
                 if self.is_listed(job)]
        found.sort(key=lambda posting: posting.posted_at, reverse=True)
        return found[:MAX_PER_BOARD]


class GreenhouseBoard(JobBoard):
    """A company's board on Greenhouse, read from the public Job Board API."""

    site = "greenhouse"

    def api_url(self):
        return f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs?content=true"

    def to_posting(self, job):
        title = job.get("title") or ""
        departments = job.get("departments") or [{}]
        return Posting(
            site=self.site, board=self.company, job_id=str(job["id"]),
            company=job.get("company_name") or self.company.title(), title=title,
            # The company's own careers page can't be filled, so link the Greenhouse page
            url=f"https://job-boards.greenhouse.io/{self.company}/jobs/{job['id']}",
            location=(job.get("location") or {}).get("name") or "",
            department=departments[0].get("name") or "",
            internship=bool(INTERNSHIP.search(title)),
            posted_at=job.get("first_published") or job.get("updated_at") or "",
            text=plain_text(job.get("content")))

    def read_form(self, posting):
        return self.read_json(greenhouse_form.API_URL.format(company=self.company,
                                                             job_id=posting.job_id))

    def required_questions(self, form):
        return sum(1 for question in form.get("questions") or [] if question.get("required"))


class AshbyBoard(JobBoard):
    """A company's board on Ashby, read from the public posting API."""

    site = "ashby"

    def api_url(self):
        return f"https://api.ashbyhq.com/posting-api/job-board/{self.company}"

    def is_listed(self, job):
        return job.get("isListed", True)

    def to_posting(self, job):
        title = job.get("title") or ""
        return Posting(
            site=self.site, board=self.company, job_id=str(job["id"]),
            company=self.company.title(), title=title,
            url=f"https://jobs.ashbyhq.com/{self.company}/{job['id']}",
            location=job.get("location") or "",
            department=job.get("department") or "",
            internship=job.get("employmentType") == "Intern" or bool(INTERNSHIP.search(title)),
            posted_at=job.get("publishedAt") or "",
            text=plain_text(job.get("descriptionPlain")))

    def read_form(self, posting):
        return ashby_form.fetch_posting(self.company, posting.job_id)

    def required_questions(self, form):
        sections = (form.get("applicationForm") or {}).get("sections") or []
        return sum(1 for section in sections for entry in section.get("fieldEntries") or []
                   if entry.get("isRequired") and not entry.get("isHidden"))


BOARDS = {"greenhouse": GreenhouseBoard, "ashby": AshbyBoard}


def company_boards():
    """Return a board for every company in COMPANY_BOARDS."""
    return [BOARDS[site](company) for site, companies in COMPANY_BOARDS.items()
            for company in companies]
