"""Tests for ranking postings by how well they fit the applicant."""
from agent.jobs.fit_ranker import FEED_SIZE, MAX_PER_COMPANY, FitRanker
from agent.jobs.job_board import Posting


def posting(title, company="Acme", **details):
    """Return a Greenhouse posting with this title."""
    job_id = details.pop("job_id", title)
    return Posting(site="greenhouse", board=company.lower(), job_id=job_id, company=company,
                   title=title, url="", **details)


STUDENT = FitRanker(skills=["Python", "SQL", "C"], interests=["Software Engineering Intern"],
                    places=["Troy, NY", "Remote (US)"])


def test_best_fit_comes_first():
    """A matching internship outranks a matching full-time job, and both outrank the rest."""
    intern = posting("Software Engineer Intern", internship=True, location="Troy, New York",
                     text="We use Python and SQL every day.")
    full_time = posting("Software Engineer", text="Python")
    senior = posting("Senior Software Engineer", text="Python")
    other = posting("Account Executive", location="London")
    ranked = STUDENT.rank([other, senior, full_time, intern])
    assert [job.title for _fit, job in ranked] == [
        "Software Engineer Intern", "Software Engineer", "Senior Software Engineer",
        "Account Executive"]
    best = ranked[0][0]
    assert best.score == 40 + 16 + 18 + 10
    assert best.reasons == ["Close to Software Engineering Intern", "Asks for Python, SQL",
                            "Internship", "In Troy, New York"]
    assert ranked[-1][0].score == 9 and ranked[-1][0].reasons == []


def test_skills_match_whole_words_only():
    """The skill "C" isn't found inside "CSS" or "C++"."""
    fit = STUDENT.fit(posting("Designer", text="CSS and C++ experience"))
    assert not any(reason.startswith("Asks for") for reason in fit.reasons)
    assert "Asks for C" in STUDENT.fit(posting("Designer", text="Embedded C, mostly")).reasons


def test_preferences_decide_the_level():
    """Someone who only wants full-time work gets no points for an internship."""
    full_time_only = FitRanker(wants_internship=False)
    assert full_time_only.fit(posting("Intern", internship=True)).score == 0
    assert full_time_only.fit(posting("Analyst")).score == 18
    assert full_time_only.fit(posting("Staff Analyst")).score == 0


def test_newest_first_among_equals_and_no_company_takes_over():
    """Equal fits are ordered by date, one company gets MAX_PER_COMPANY, and the list is capped."""
    older = posting("Analyst", company="Old", posted_at="2026-10-01")
    newer = posting("Analyst", company="New", posted_at="2026-11-01")
    assert [job.company for _fit, job in FitRanker().rank([older, newer])] == ["New", "Old"]

    crowd = [posting("Analyst", job_id=str(n)) for n in range(MAX_PER_COMPANY + 5)]
    assert len(FitRanker().rank(crowd)) == MAX_PER_COMPANY
    many = [posting("Analyst", company=f"Company {n}") for n in range(FEED_SIZE + 20)]
    assert len(FitRanker().rank(many)) == FEED_SIZE
