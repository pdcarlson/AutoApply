"""Tests for link detection (US5: one link per ATS queues, LinkedIn rejected)."""
from app.services.ats import company_from_url, detect_ats


def test_greenhouse():
    assert detect_ats("https://boards.greenhouse.io/northwinddata/jobs/4412093") == "greenhouse"
    assert detect_ats("https://job-boards.greenhouse.io/northwinddata/jobs/1") == "greenhouse"


def test_lever():
    assert detect_ats("https://jobs.lever.co/kestrelhealth/abc-123") == "lever"


def test_ashby():
    assert detect_ats("https://jobs.ashbyhq.com/brightline/xyz") == "ashby"


def test_unsupported():
    assert detect_ats("https://www.linkedin.com/jobs/view/123") is None
    assert detect_ats("not a url") is None


def test_company_slug():
    assert company_from_url("https://jobs.lever.co/kestrelhealth/abc-123") == "kestrelhealth"
    assert company_from_url("https://jobs.lever.co/") == ""
