"""Tells a role's title from its organization by the words each uses."""
import re

from server.resume.line_text import clean

TITLE_WORDS = {
    "engineer", "developer", "designer", "manager", "director", "intern", "internship", "analyst",
    "scientist", "specialist", "coordinator", "assistant", "associate", "consultant",
    "architect", "administrator", "lead", "head", "president", "vice", "officer", "chief", "ceo",
    "cto", "cfo", "coo", "vp", "founder", "co-founder", "teacher", "instructor", "professor",
    "lecturer", "tutor", "researcher", "fellow", "technician", "nurse", "rn", "physician",
    "accountant", "controller", "auditor", "representative", "executive", "supervisor",
    "volunteer", "member", "chair", "treasurer", "secretary", "editor", "writer", "mentor",
    "counselor", "co-op", "coop", "trainee", "apprentice", "clerk", "cashier", "agent",
    "programmer", "strategist", "marketer", "recruiter", "attorney", "paralegal", "ta", "sergeant",
    "advisor", "adviser", "organizer", "principal", "owner", "partner", "senior", "junior", "sr",
    "jr", "captain", "leader", "reliability", "devops", "sre", "sales", "operations",
}
ORG_WORDS = {
    "inc", "llc", "llp", "ltd", "corp", "corporation", "company", "co", "group", "university",
    "college", "institute", "school", "academy", "hospital", "health", "healthcare", "bank",
    "lab", "labs", "laboratory", "department", "agency", "foundation", "association", "society",
    "club", "council", "center", "centre", "studio", "studios", "partners", "technologies",
    "solutions", "services", "consulting", "ventures", "holdings", "capital", "motors",
    "brands", "foods", "products", "logistics", "government", "army", "navy", "federal", "city",
    "county", "administration", "division", "fund", "industries", "supply", "architects",
    "roasters",
}


def _role_words(text: str) -> list[str]:
    """Return the lowercase words of `text`, punctuation trimmed."""
    return [word.strip(".,()'’").lower() for word in re.findall(r"[A-Za-z][\w.&'’-]*", text)]


def title_word_count(text: str) -> int:
    """Return how many title words ("Engineer", "Intern") `text` has."""
    return sum(word in TITLE_WORDS for word in _role_words(text))


def role_score(text: str) -> int:
    """Return how title-like `text` is: title words count up, organization words count down."""
    return title_word_count(text) - sum(word in ORG_WORDS for word in _role_words(text))


def split_org_title(text: str) -> tuple[str, str]:
    """Split "Org - Title", "Title, Org" or "Title at Org" into (org, title).

    The side with more title words than organization words is the title; on a tie it is
    "Org - Title" and "Title, Org".
    """
    if re.search(r"\s+at\s+", text):
        title, org = re.split(r"\s+at\s+", text, maxsplit=1)
        return clean(org), clean(title)
    parts = re.split(r"\s+[-–—|@·]\s+", text, maxsplit=1)
    if len(parts) == 2:
        first, second = parts
        if role_score(first) > role_score(second):
            return clean(second), clean(first)
        return clean(first), clean(second)
    if "," in text:
        first, second = text.split(",", 1)
        if role_score(second) > role_score(first):
            return clean(first), clean(second)
        return clean(second), clean(first)
    return ("", clean(text)) if role_score(text) > 0 else (clean(text), "")
