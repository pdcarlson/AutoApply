"""Protected steps: CAPTCHAs, sign-ins, passwords and Social Security numbers (US8).

The agent never types into these. A form that has one is filled everywhere else and then
handed to the applicant, who does that step in the form's own window.

Only what describes a field is read (label, name, id, type, autocomplete, placeholder), never
what's typed in it, so an SSN or a password can't reach the logs or the saved data.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError

CAPTCHA = "captcha"
SSN = "ssn"
PASSWORD = "password"
LOGIN = "login"

MIN_CAPTCHA_PX = 30  # smaller frames are a CAPTCHA's hidden helpers, not something to solve


@dataclass(frozen=True)
class PageField:
    """What describes one input on the page."""

    label: str = ""
    name: str = ""
    element_id: str = ""
    input_type: str = "text"
    autocomplete: str = ""
    placeholder: str = ""

    def text(self):
        """Return everything that describes the field as one lowercase string.

        Underscores and dashes become spaces, so social_security_number reads the same as
        the label "Social Security number".
        """
        joined = " ".join([self.label, self.name, self.element_id, self.placeholder])
        return re.sub(r"[_\-]+", " ", joined).lower()


@dataclass(frozen=True)
class Handoff:
    """One step the applicant has to do themselves, and why."""

    kind: str  # captcha, ssn, password or login
    label: str
    message: str


class ProtectedCheck(ABC):
    """One kind of field the agent must never fill."""

    kind = ""
    message = ""

    @abstractmethod
    def matches(self, page_field):
        """Return True if the agent must not type into this field."""

    def handoff(self, page_field):
        """Return the Handoff for a field this check matched."""
        return Handoff(self.kind, page_field.label or page_field.name, self.message)


class CaptchaCheck(ProtectedCheck):
    """reCAPTCHA, hCaptcha and Cloudflare Turnstile.

    These live in an iframe, so scan_page looks at frame addresses too.
    """

    kind = CAPTCHA
    message = "This form has a CAPTCHA, and the agent never solves those."
    FRAME_HOSTS = ("google.com/recaptcha", "recaptcha.net", "hcaptcha.com",
                   "challenges.cloudflare.com")

    def matches(self, page_field):
        return "captcha" in page_field.text() or "turnstile" in page_field.text()

    def matches_frame(self, url):
        """Return True for a CAPTCHA frame that shows something to solve.

        An invisible CAPTCHA only puts a badge on the page, which is nothing to solve.
        """
        url = url.lower()
        return any(host in url for host in self.FRAME_HOSTS) and "size=invisible" not in url


class SsnCheck(ProtectedCheck):
    """Social Security numbers, which are never filled in or saved."""

    kind = SSN
    message = "This form asks for a Social Security number, which AutoApply never fills or saves."
    PATTERN = re.compile(r"\bssn\b|social security|social insurance number|\bsin number\b")

    def matches(self, page_field):
        return bool(self.PATTERN.search(page_field.text()))


class PasswordCheck(ProtectedCheck):
    """Any password box, which also means the form wants an account."""

    kind = PASSWORD
    message = "This form wants a password, and the agent never types those."

    def matches(self, page_field):
        return (page_field.input_type.lower() == "password"
                or page_field.autocomplete.lower() in ("current-password", "new-password")
                or page_field.label.strip().lower().rstrip("*: ") == "password")


class LoginCheck(ProtectedCheck):
    """Sign-in and verification steps other than the password box itself.

    Kept narrow on purpose: "GitHub username" is a normal application question, so only a
    bare "Username" field counts as a sign-in.
    """

    kind = LOGIN
    message = "This form needs a sign-in or a verification code."
    BARE_LABELS = ("username", "user name", "login", "log in", "sign in", "user id")
    CODE_PATTERN = re.compile(
        r"verification code|one time (pass)?code|security code|\b2fa\b|\bmfa\b|\botp\b")

    def matches(self, page_field):
        if page_field.autocomplete.lower() in ("username", "one-time-code"):
            return True
        if page_field.label.strip().lower().rstrip("*: ") in self.BARE_LABELS:
            return True
        return bool(self.CODE_PATTERN.search(page_field.text()))


# Reads what describes each visible field, never its value
VISIBLE_FIELDS_JS = """
() => Array.from(document.querySelectorAll('input, textarea, select'))
  .filter((el) => el.type !== 'hidden' && el.getClientRects().length > 0)
  .map((el) => {
    const labelledBy = el.getAttribute('aria-labelledby');
    const byId = labelledBy ? document.getElementById(labelledBy) : null;
    const label = (el.labels && el.labels[0] && el.labels[0].innerText)
      || el.getAttribute('aria-label') || (byId && byId.innerText) || '';
    return {
      label: label.trim(),
      name: el.getAttribute('name') || '',
      element_id: el.id || '',
      input_type: (el.getAttribute('type') || el.tagName).toLowerCase(),
      autocomplete: el.getAttribute('autocomplete') || '',
      placeholder: el.getAttribute('placeholder') || '',
    };
  })
"""


class ProtectedFieldDetector:
    """Finds every step on a form that has to go to the applicant."""

    def __init__(self, checks=None):
        self.checks = checks if checks is not None else [
            CaptchaCheck(), SsnCheck(), PasswordCheck(), LoginCheck()]

    def check_field(self, page_field):
        """Return the Handoff for this field, or None if the agent may fill it."""
        for check in self.checks:
            if check.matches(page_field):
                return check.handoff(page_field)
        return None

    def check_question(self, form_field):
        """Return the Handoff for a FormField read from the site, or None."""
        return self.check_field(PageField(label=form_field.label, name=form_field.key))

    def scan_page(self, page):
        """Return a Handoff for every protected field and CAPTCHA showing on the open page."""
        fields = [PageField(**raw) for raw in page.evaluate(VISIBLE_FIELDS_JS)]
        handoffs = [found for found in map(self.check_field, fields) if found is not None]
        return handoffs + self.scan_captchas(page)

    def scan_captchas(self, page):
        """Return a Handoff if a CAPTCHA is showing on the open page."""
        for check in self.checks:
            if isinstance(check, CaptchaCheck) and any(
                    check.matches_frame(frame.url) and frame_shows(frame)
                    for frame in page.frames):
                return [Handoff(CAPTCHA, "CAPTCHA", check.message)]
        return []


def frame_shows(frame):
    """Return True if the frame is on screen and big enough to hold something to solve."""
    try:
        element = frame.frame_element()
        box = element.bounding_box() if element.is_visible() else None
    except PlaywrightError:
        return False
    return bool(box) and box["width"] >= MIN_CAPTCHA_PX and box["height"] >= MIN_CAPTCHA_PX


def merge(handoffs, found):
    """Add the newly found Handoffs to the list, skipping ones already there."""
    for handoff in found:
        if handoff not in handoffs:
            handoffs.append(handoff)
    return handoffs


def handoff_reason(handoffs):
    """Return one plain reason for the applicant, with one sentence per kind of step."""
    seen = []
    for handoff in handoffs:
        if handoff.message not in seen:
            seen.append(handoff.message)
    return " ".join(seen)
