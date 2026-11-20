"""Job board routes: the ranked postings, and applying to one."""
import pytest

from agent.jobs.job_board import GreenhouseBoard
from server.tests.job_helpers import (FAKE_ASHBY_URL, FAKE_URL, add_job, job_detail,
                                      refuse_network, seed_fake_form_answers, set_up_profile)

POSTING_KEYS = {"id", "company", "role", "location", "ats", "url", "postedAt", "internship",
                "fit", "status", "jobId"}
FAKE_POSTING = "greenhouse-fakecompany-1001"


@pytest.fixture(name="offline", autouse=True)
def fixture_offline(monkeypatch):
    """Nothing in these tests may go online: the fake boards are local files."""
    refuse_network(monkeypatch, "agent.jobs.job_board")


def postings(client) -> list[dict]:
    """Return the postings GET /postings lists."""
    response = client.get("/api/postings")
    assert response.status_code == 200, response.text
    return response.json()["postings"]


def test_lists_postings_from_both_sites(signed_in, app):
    """The fake Greenhouse and Ashby boards are both listed, in the API shape."""
    app.state.job_feed.refresh()
    body = signed_in.get("/api/postings").json()
    assert body["fetchedAt"] and body["refreshing"] is False
    listed = body["postings"]
    assert {posting["ats"] for posting in listed} == {"Greenhouse", "Ashby"}
    assert all(set(posting) == POSTING_KEYS for posting in listed)
    greenhouse = next(posting for posting in listed if posting["ats"] == "Greenhouse")
    assert greenhouse["id"] == FAKE_POSTING and greenhouse["url"] == FAKE_URL
    assert (greenhouse["company"], greenhouse["role"]) == ("Fake Company",
                                                           "Software Engineering Intern")
    assert greenhouse["internship"] and greenhouse["status"] == "open"
    assert {posting["url"] for posting in listed} == {FAKE_URL, FAKE_ASHBY_URL}


def test_first_request_collects_the_postings(signed_in, app):
    """An empty feed starts collecting by itself, and the list fills in."""
    assert app.state.job_feed.postings == []
    signed_in.get("/api/postings")
    for _ in range(200):
        body = signed_in.get("/api/postings").json()
        if body["postings"] and not body["refreshing"]:
            break
    assert len(body["postings"]) == 2


def test_postings_are_ranked_by_the_profile(client, app):
    """The example resume's skills and experience put the engineering internship first."""
    set_up_profile(client)
    feed = app.state.job_feed
    feed.boards = [GreenhouseBoard("acme", data={"jobs": [
        {"id": 1, "title": "Account Executive", "company_name": "Acme"},
        {"id": 2, "title": "Software Engineering Intern", "company_name": "Acme",
         "content": "Python"},
    ]})]
    feed.refresh()
    first, last = postings(client)
    assert first["role"] == "Software Engineering Intern" and last["role"] == "Account Executive"
    assert first["fit"]["score"] > last["fit"]["score"]
    assert "Internship" in first["fit"]["reasons"]


def test_apply_adds_the_job_and_queues_it(client, app):
    """Applying to a posting adds it to the Inbox, queues it, and marks it in_inbox."""
    set_up_profile(client)
    app.state.job_feed.refresh()
    response = client.post(f"/api/postings/{FAKE_POSTING}/apply")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deferred"] is False
    job = body["job"]
    assert (job["state"], job["source"], job["url"]) == ("queued", "matched", FAKE_URL)
    assert job["postedAt"]
    stored = app.state.store.read("jobs")[0]
    assert [event["text"] for event in stored["timeline"]] == ["You picked it from Jobs",
                                                               "You pressed Apply"]
    listed = next(posting for posting in postings(client) if posting["id"] == FAKE_POSTING)
    assert (listed["status"], listed["jobId"]) == ("in_inbox", job["id"])
    # Applying to it again is refused, the same as pasting its link again.
    again = client.post(f"/api/postings/{FAKE_POSTING}/apply")
    assert again.status_code == 409 and again.json()["code"] == "already_in_inbox"


def test_apply_waits_for_tomorrow_at_the_daily_limit(client, app):
    """At the daily limit a posting applied to waits."""
    set_up_profile(client)
    app.state.job_feed.refresh()
    assert client.patch("/api/settings", json={"dailyLimit": 1}).status_code == 200
    held = add_job(client, FAKE_ASHBY_URL)
    assert client.post("/api/jobs/apply", json={"jobIds": [held["id"]]}).status_code == 200
    body = client.post(f"/api/postings/{FAKE_POSTING}/apply").json()
    assert body["deferred"] is True and body["job"]["state"] == "waiting"


def test_apply_needs_a_confirmed_profile_and_a_known_posting(signed_in, app):
    """Applying needs a confirmed profile and a posting the feed knows."""
    app.state.job_feed.refresh()
    response = signed_in.post(f"/api/postings/{FAKE_POSTING}/apply")
    assert response.status_code == 409 and response.json()["code"] == "profile_not_confirmed"
    assert app.state.store.read("jobs") == []
    assert signed_in.post("/api/postings/greenhouse-nobody-1/apply").status_code == 404


def test_applying_to_postings_one_after_another_queues_them_in_order(client, app):
    """Postings applied to one after another queue in that order."""
    set_up_profile(client)
    app.state.job_feed.refresh()
    first = client.post(f"/api/postings/{FAKE_POSTING}/apply").json()["job"]
    ashby = next(posting for posting in postings(client) if posting["ats"] == "Ashby")
    second = client.post(f"/api/postings/{ashby['id']}/apply").json()["job"]
    assert (first["state"], second["state"]) == ("queued", "queued")
    assert client.get("/api/agent/status").json()["queue"] == [first["id"], second["id"]]
    assert {posting["status"] for posting in postings(client)} == {"in_inbox"}


def test_the_agent_fills_a_job_picked_from_the_board(client, app):
    """A posting applied to from Jobs is filled and held for review, like a pasted link."""
    set_up_profile(client)
    seed_fake_form_answers(app)
    app.state.job_feed.refresh()
    job = client.post(f"/api/postings/{FAKE_POSTING}/apply").json()["job"]
    assert app.state.worker.run_next() == job["id"]
    detail = job_detail(client, job["id"])
    assert detail["state"] == "ready" and detail["source"] == "matched"
    assert detail["progress"]["filled"] == detail["progress"]["total"]
