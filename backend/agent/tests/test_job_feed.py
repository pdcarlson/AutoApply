"""Tests for reading company job boards and keeping the collected postings."""
import json
from pathlib import Path

from agent.jobs.job_board import AshbyBoard, GreenhouseBoard, JobBoard, company_boards
from agent.jobs.job_feed import JobFeed
from agent.jobs.job_link import JobLink

FAKE_FORMS = Path(__file__).parent / "fake_forms"

GREENHOUSE_JOBS = {"jobs": [
    {"id": 11, "title": "Software Engineer Intern (Summer 2027)", "company_name": "Acme",
     "location": {"name": "Troy, NY"}, "departments": [{"name": "Engineering"}],
     "first_published": "2026-11-01T09:00:00-05:00",
     "content": "&lt;p&gt;You know &lt;b&gt;Python&lt;/b&gt; and SQL.&lt;/p&gt;"},
    {"id": 12, "title": "Senior Accountant", "location": {"name": "Remote"},
     "first_published": "2026-11-10T09:00:00-05:00"},
]}
ASHBY_JOBS = {"jobs": [
    {"id": "aa-1", "title": "Data Analyst", "location": "New York", "department": "Data",
     "employmentType": "Intern", "isListed": True, "publishedAt": "2026-11-05T00:00:00+00:00",
     "descriptionPlain": "SQL and dashboards"},
    {"id": "aa-2", "title": "Hidden role", "isListed": False},
]}


class DownBoard(JobBoard):
    """A board whose site doesn't answer."""

    site = "greenhouse"

    def api_url(self):
        return ""

    def to_posting(self, job):
        return job

    def read_form(self, posting):
        raise OSError("offline")

    def required_questions(self, form):
        return 0

    def postings(self):
        raise OSError("offline")


class SavedFormsBoard(GreenhouseBoard):
    """A Greenhouse board whose forms are saved data: job id -> its required flags."""

    forms = {"11": [True, True, False], "12": [True], "13": [True, True, True]}

    def read_form(self, posting):
        if posting.job_id not in self.forms:
            raise OSError("no form")
        return {"questions": [{"required": flag} for flag in self.forms[posting.job_id]]}


def test_greenhouse_postings_come_out_in_one_format():
    """A Greenhouse job becomes a Posting with plain text and a link the agent can fill."""
    newest, intern = GreenhouseBoard("acme", data=GREENHOUSE_JOBS).postings()
    assert newest.title == "Senior Accountant" and not newest.internship
    assert (intern.company, intern.location, intern.department) == ("Acme", "Troy, NY",
                                                                    "Engineering")
    assert intern.internship and intern.text == "You know Python and SQL."
    assert intern.posting_id == "greenhouse-acme-11"
    link = JobLink.parse(intern.url)
    assert (link.site, link.company, link.job_id) == ("greenhouse", "acme", "11")


def test_ashby_postings_skip_unlisted_jobs():
    """An Ashby job becomes the same kind of Posting, and unlisted jobs are left out."""
    [posting] = AshbyBoard("acme", data=ASHBY_JOBS).postings()
    assert (posting.company, posting.title, posting.location) == ("Acme", "Data Analyst",
                                                                  "New York")
    assert posting.internship and posting.text == "SQL and dashboards"
    link = JobLink.parse(posting.url)
    assert (link.site, link.company, link.job_id) == ("ashby", "acme", "aa-1")


def test_company_boards_cover_both_sites():
    """The built-in list has boards on Greenhouse and on Ashby."""
    assert {board.site for board in company_boards()} == {"greenhouse", "ashby"}


def test_feed_collects_saves_and_reloads(tmp_path):
    """A refresh collects every board, and a new feed on the same file starts with them."""
    path = tmp_path / "job_feed.json"
    feed = JobFeed(path, keep=None, boards=[GreenhouseBoard("acme", data=GREENHOUSE_JOBS),
                                            AshbyBoard("acme", data=ASHBY_JOBS),
                                            DownBoard("gone")])
    assert feed.is_stale() and feed.postings == []
    feed.refresh()
    assert len(feed.postings) == 3 and not feed.is_stale()
    assert feed.find("ashby-acme-aa-1").title == "Data Analyst"
    assert feed.find("ashby-acme-aa-2") is None

    again = JobFeed(path, boards=[])
    assert again.postings == feed.postings and not again.is_stale()


def test_feed_keeps_its_postings_when_every_site_fails(tmp_path):
    """Going offline doesn't empty the board."""
    feed = JobFeed(tmp_path / "job_feed.json", keep=None,
                   boards=[GreenhouseBoard("acme", data=GREENHOUSE_JOBS)])
    feed.refresh()
    feed.boards = [DownBoard("gone")]
    feed.refresh()
    assert len(feed.postings) == 2


def test_required_questions_are_counted_on_both_sites():
    """Each board counts the required questions in its own site's form data."""
    greenhouse = json.loads((FAKE_FORMS / "greenhouse_api.json").read_text(encoding="utf-8"))
    ashby = json.loads((FAKE_FORMS / "ashby_api.json").read_text(encoding="utf-8"))
    assert GreenhouseBoard("acme").required_questions(greenhouse) == sum(
        1 for question in greenhouse["questions"] if question["required"])
    assert AshbyBoard("acme").required_questions(ashby) == 8
    assert AshbyBoard("acme").required_questions({}) == 0


def test_feed_keeps_only_the_shortest_forms(tmp_path):
    """With `keep` set, the postings with the fewest required questions stay, shortest first,
    and one whose form can't be read is dropped."""
    jobs = {"jobs": [{"id": number, "title": f"Job {number}"} for number in (11, 12, 13, 14)]}
    feed = JobFeed(tmp_path / "job_feed.json", keep=2,
                   boards=[SavedFormsBoard("acme", data=jobs)])
    feed.refresh()
    assert [posting.job_id for posting in feed.postings] == ["12", "11"]
