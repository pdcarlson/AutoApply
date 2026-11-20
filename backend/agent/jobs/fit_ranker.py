"""Ranks postings by how well they fit the applicant."""
import re
from dataclasses import dataclass, field

from agent.jobs.job_board import Posting

FEED_SIZE = 200       # the most postings one ranking hands back
MAX_PER_COMPANY = 10  # so one big company can't take over the list

ROLE_POINTS = 40
SKILL_POINTS = 8      # for each skill the posting mentions, up to MAX_SKILLS
MAX_SKILLS = 4
LEVEL_POINTS = 18
PLACE_POINTS = 10
# The share of an interest's words a title needs before it's named as a reason
CLOSE_ROLE_SHARE = 0.5
# Words are cut to this length, so "engineer" and "engineering" count as the same word
WORD_STEM_LENGTH = 6

SENIOR = re.compile(r"\b(senior|sr|staff|principal|lead|manager|director|head|vp)\b",
                    re.IGNORECASE)
# Words in a job title that say nothing about the kind of work
FILLER = {"and", "the", "for", "intern", "internship", "summer", "fall", "spring", "winter",
          "new", "grad", "junior", "associate", "senior"}


@dataclass
class Fit:
    """How well one posting fits, and why."""

    score: int = 0  # 0 to 100
    reasons: list[str] = field(default_factory=list)


def key_words(text: str) -> set[str]:
    """Return the shortened words that say what kind of work a title is."""
    return {word[:WORD_STEM_LENGTH] for word in re.findall(r"[a-z+#]+", text.lower())
            if len(word) > 2 and word not in FILLER}


class FitRanker:
    """Scores postings against one applicant's skills, interests and places."""

    def __init__(self, skills=(), interests=(), places=(), wants_internship: bool = True,
                 wants_full_time: bool = True):
        """Clean up the applicant's skills, interests and places, and build the skill pattern."""
        self.skills = [skill for skill in skills if skill.strip()]
        # One pattern for every skill, longest first so "C++" isn't read as "C"
        longest_first = sorted(map(re.escape, self.skills), key=len, reverse=True)
        self.skill_pattern = re.compile(
            rf"(?<![\w+#])({'|'.join(longest_first)})(?![\w+#])", re.IGNORECASE)
        # Job titles and fields the applicant wants, like "Software Engineering"
        self.interests = [interest for interest in interests if key_words(interest)]
        # Only the city is compared, so "Troy, NY" matches "Troy, New York"
        self.places = [re.split(r"[,(]", place)[0].strip().lower() for place in places]
        self.wants_internship = wants_internship
        self.wants_full_time = wants_full_time

    def fit(self, posting: Posting) -> Fit:
        """Return the posting's Fit."""
        fit = Fit()
        for points, reason in (self._role(posting), self._skill(posting),
                               self._level(posting), self._place(posting)):
            fit.score += points
            if reason:
                fit.reasons.append(reason)
        return fit

    def _role(self, posting: Posting) -> tuple[int, str]:
        """Score how close the job title is to a role the applicant wants."""
        title = key_words(f"{posting.title} {posting.department}")
        best, share = "", 0.0
        for interest in self.interests:
            words = key_words(interest)
            shared = len(words & title) / len(words)
            if shared > share:
                best, share = interest, shared
        return round(ROLE_POINTS * share), f"Close to {best}" if share >= CLOSE_ROLE_SHARE else ""

    def _skill(self, posting: Posting) -> tuple[int, str]:
        """Score how many of the applicant's skills the posting mentions."""
        if not self.skills:
            return 0, ""
        mentioned = {skill.lower() for skill in
                     self.skill_pattern.findall(f"{posting.title} {posting.text}")}
        found = [skill for skill in self.skills if skill.lower() in mentioned][:MAX_SKILLS]
        return SKILL_POINTS * len(found), "Asks for " + ", ".join(found) if found else ""

    def _level(self, posting: Posting) -> tuple[int, str]:
        """Score whether the job is at the applicant's level."""
        if posting.internship:
            return (LEVEL_POINTS, "Internship") if self.wants_internship else (0, "")
        if not self.wants_full_time or SENIOR.search(posting.title):
            return 0, ""
        # Someone looking for internships sees those above the full-time jobs
        return LEVEL_POINTS // 2 if self.wants_internship else LEVEL_POINTS, ""

    def _place(self, posting: Posting) -> tuple[int, str]:
        """Score whether the job is somewhere the applicant wants to work."""
        location = posting.location.lower()
        if any(place and place in location for place in self.places):
            return PLACE_POINTS, f"In {posting.location}"
        return 0, ""

    def rank(self, postings: list[Posting]) -> list[tuple[Fit, Posting]]:
        """Return up to FEED_SIZE (Fit, Posting) pairs, best fit first, then newest first.

        No more than MAX_PER_COMPANY come from one company.
        """
        newest = sorted(postings, key=lambda posting: posting.posted_at, reverse=True)
        scored = sorted(((self.fit(posting), posting) for posting in newest),
                        key=lambda pair: pair[0].score, reverse=True)
        ranked, per_company = [], {}
        for fit, posting in scored:
            count = per_company.get(posting.company, 0)
            if count < MAX_PER_COMPANY:
                per_company[posting.company] = count + 1
                ranked.append((fit, posting))
        return ranked[:FEED_SIZE]
