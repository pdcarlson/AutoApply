"""Reads a person's name, email, phone, place and links from resume lines."""
import re

from server.names import split_name
from server.resume.patterns import (DEGREE_RE, EMAIL_RE, NAME_WORD_RE, PHONE_RE, SCHOOL_RE,
                                    SEGMENT_RE, URL_RE)
from server.resume.places import LOCATION_RE, find_location

_CREDENTIALS_RE = re.compile(r"(?:,\s*(?:[A-Z]{2,5}|(?:[A-Z]\.){1,3}[A-Z]?\.?))*,?\s*$")
# "Location: Troy, MI", "Email: jo@example.com"
_ITEM_LABEL_RE = re.compile(r"^[A-Za-z][\w ]{0,15}:\s*")
# An icon font can leave its glyph's name in front: "inlinkedin.com/in/x", "ghgithub.com/x"
_KNOWN_SITE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin|github)\.com\S*", re.I)


def segments(line: str) -> list[str]:
    """Return the line's pieces between separators such as "|", "•" and wide gaps."""
    return [segment.strip() for segment in SEGMENT_RE.split(line) if segment and segment.strip()]


def is_contact_item(segment: str) -> bool:
    """Return True when all of `segment` is an email, phone, URL or place (or "Label: ...")."""
    segment = segment.strip().strip("\"'")
    label = _ITEM_LABEL_RE.match(segment)
    if label:
        segment = segment[label.end():].strip("\"'")
    return bool(EMAIL_RE.fullmatch(segment) or PHONE_RE.fullmatch(segment)
                or URL_RE.fullmatch(segment)
                or (find_location(segment) and LOCATION_RE.fullmatch(segment)))


def is_contact_line(line: str, early: bool) -> bool:
    """Return True for a line of contact items, or (near the top) any line with email or phone."""
    pieces = segments(line)
    if pieces and all(is_contact_item(piece) for piece in pieces):
        return True
    return early and bool(EMAIL_RE.search(line) or PHONE_RE.search(line))


def is_name(line: str) -> bool:
    """Return True when the line looks like a person's name: 2 to 4 capitalized words."""
    words = line.split()
    if not 2 <= len(words) <= 4 or re.search(r"[\d@|,]", line):
        return False
    if SCHOOL_RE.search(line) or DEGREE_RE.search(line):
        return False
    return all(NAME_WORD_RE.match(word) for word in words)


def name_text(text: str) -> str:
    """Return the bare name from "Maria Santos,", "Anthony DiMarco, P.E." or "kenji_watanabe"."""
    text = text.strip()
    if re.fullmatch(r"[a-z]+[_.][a-z]+", text):
        return text.replace("_", " ").replace(".", " ").title()
    text = _CREDENTIALS_RE.sub("", text).strip()
    return text.title() if text.isupper() else text


def _full_url(text: str) -> str:
    """Return the link as a full https:// URL."""
    text = text.rstrip(".")
    known = _KNOWN_SITE_RE.search(text)
    if known:
        text = known.group(0)
    return text if re.match(r"https?://", text, re.I) else f"https://{text}"


def _link_key(url: str) -> str:
    """Return which fixed profile link a URL fills: linkedin, github or web."""
    lowered = url.lower()
    if "linkedin.com" in lowered:
        return "linkedin"
    return "github" if "github.com" in lowered else "web"


class Contact:
    """The contact details found so far, filled in line by line."""

    def __init__(self):
        self.name = ""
        self.email = ""
        self.phone = ""
        self.city = ""
        self.state = ""
        self.links: dict[str, str] = {}
        self.extra_links: list[str] = []

    def read(self, line: str) -> None:
        """Take any email, phone, links and place from the line that aren't known yet."""
        email = EMAIL_RE.search(line)
        if email and not self.email:
            self.email = email.group(0).rstrip(".")
        rest = EMAIL_RE.sub(" ", line)
        phone = PHONE_RE.search(rest)
        if phone and not self.phone:
            self.phone = re.sub(r"\s+", " ", phone.group(0).strip())
        for match in URL_RE.finditer(rest):
            self._add_link(_full_url(match.group(0)))
        for segment in segments(rest):
            place = find_location(_ITEM_LABEL_RE.sub("", segment))
            if place and not self.city:
                self.city, self.state = place

    def _add_link(self, url: str) -> None:
        """Keep the first link of each fixed kind, and every other new one as an extra."""
        key = _link_key(url)
        if key not in self.links:
            self.links[key] = url
        elif url not in self.links.values() and url not in self.extra_links:
            self.extra_links.append(url)

    def count(self) -> int:
        """Return how many contact fields were found."""
        return (sum(bool(value) for value in (self.name, self.email, self.phone))
                + bool(self.city) + len(self.links) + len(self.extra_links))

    def to_json(self) -> dict:
        """Return the Profile fields found, in the API's camelCase."""
        out = {}
        if self.name:
            out["firstName"], out["middleName"], out["lastName"] = split_name(self.name)
        for key in ("email", "phone", "city", "state"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        if self.links or self.extra_links:
            out["links"] = self._links_json()
        return out

    def _links_json(self) -> list[dict]:
        """Return the three fixed profile links, then one link per extra URL."""
        links = [
            {"id": "web", "label": "Website / portfolio", "url": self.links.get("web", ""),
             "fixed": True},
            {"id": "linkedin", "label": "LinkedIn", "url": self.links.get("linkedin", ""),
             "fixed": True},
            {"id": "github", "label": "GitHub", "url": self.links.get("github", ""),
             "fixed": True},
        ]
        for number, url in enumerate(self.extra_links, 1):
            host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
            links.append({"id": f"link-{number}", "label": host, "url": url, "fixed": False})
        return links
