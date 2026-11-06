"""Tests for reading job links."""
import pytest

from agent.jobs.job_link import JobLink, UnsupportedLink


def test_greenhouse_hosts_mean_the_same_job():
    """Both Greenhouse hosts and the embed link parse to the same job."""
    links = [
        JobLink.parse("https://boards.greenhouse.io/fakecompany/jobs/12345"),
        JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/12345?gh_src=abc"),
        JobLink.parse("https://job-boards.greenhouse.io/embed/job_app?for=fakecompany&token=12345"),
    ]
    assert all(link == links[0] for link in links)
    assert links[0].site == "greenhouse"
    assert links[0].url == "https://job-boards.greenhouse.io/fakecompany/jobs/12345"


def test_lever_and_ashby_links():
    """Lever and Ashby links keep the company and job id and drop the apply page."""
    lever = JobLink.parse("https://jobs.lever.co/fakecompany/abc-123/apply")
    ashby = JobLink.parse("https://jobs.ashbyhq.com/fakecompany/def-456/application")
    assert (lever.site, lever.company, lever.job_id) == ("lever", "fakecompany", "abc-123")
    assert (ashby.site, ashby.company, ashby.job_id) == ("ashby", "fakecompany", "def-456")


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123",
    "https://boards.greenhouse.io/fakecompany",
    "https://jobs.lever.co/fakecompany",
    "not a link",
])
def test_unsupported_links(url):
    """Other sites and links that aren't one job are rejected."""
    with pytest.raises(UnsupportedLink):
        JobLink.parse(url)
