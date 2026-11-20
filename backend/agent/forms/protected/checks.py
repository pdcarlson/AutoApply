"""The kinds of field the agent must never fill: CAPTCHAs, SSNs, passwords and sign-ins."""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from agent.forms.protected.handoff import Handoff, HandoffKind


@dataclass(frozen=True)
class PageField:
    """What describes one input on the page, never what's typed in it."""

    label: str = ""
    name: str = ""
    element_id: str = ""
    input_type: str = "text"
    autocomplete: str = ""
    placeholder: str = ""

    def text(self) -> str:
        """Return everything that describes the field as one lowercase string."""
        joined = " ".join([self.label, self.name, self.element_id, self.placeholder])
        # So social_security_number reads the same as the label "Social Security number"
        return re.sub(r"[_\-]+", " ", joined).lower()

    def bare_label(self) -> str:
        """Return the label in lowercase without its required-field marks."""
        return self.label.strip().lower().rstrip("*: ")


class ProtectedCheck(ABC):
    """One kind of field the agent must never fill."""

    kind: HandoffKind
    message = ""

    @abstractmethod
    def matches(self, page_field: PageField) -> bool:
        """Return True if the agent must not type into this field."""

    def handoff(self, page_field: PageField) -> Handoff:
        """Return the Handoff for a field this check matched."""
        return Handoff(self.kind, page_field.label or page_field.name, self.message)


class CaptchaCheck(ProtectedCheck):
    """reCAPTCHA, hCaptcha and Cloudflare Turnstile, which live in a frame on the page."""

    kind = HandoffKind.CAPTCHA
    message = "This form has a CAPTCHA, and the agent never solves those."
    FRAME_HOSTS = ("google.com/recaptcha", "recaptcha.net", "hcaptcha.com",
                   "challenges.cloudflare.com")

    def matches(self, page_field: PageField) -> bool:
        """Return True for a field that names a CAPTCHA."""
        return "captcha" in page_field.text() or "turnstile" in page_field.text()

    def matches_frame(self, url: str) -> bool:
        """Return True for a CAPTCHA frame that shows something to solve."""
        url = url.lower()
        # An invisible CAPTCHA only puts a badge on the page, which is nothing to solve
        return any(host in url for host in self.FRAME_HOSTS) and "size=invisible" not in url


class SsnCheck(ProtectedCheck):
    """Social Security numbers, which are never filled in or saved."""

    kind = HandoffKind.SSN
    message = "This form asks for a Social Security number, which AutoApply never fills or saves."
    PATTERN = re.compile(r"\bssn\b|social security|social insurance number|\bsin number\b")

    def matches(self, page_field: PageField) -> bool:
        """Return True for a field that asks for a Social Security number."""
        return bool(self.PATTERN.search(page_field.text()))


class PasswordCheck(ProtectedCheck):
    """Any password box, which also means the form wants an account."""

    kind = HandoffKind.PASSWORD
    message = "This form wants a password, and the agent never types those."

    def matches(self, page_field: PageField) -> bool:
        """Return True for a password box."""
        return (page_field.input_type.lower() == "password"
                or page_field.autocomplete.lower() in ("current-password", "new-password")
                or page_field.bare_label() == "password")


class LoginCheck(ProtectedCheck):
    """Sign-in and verification steps other than the password box itself."""

    kind = HandoffKind.LOGIN
    message = "This form needs a sign-in or a verification code."
    # Kept narrow on purpose: "GitHub username" is a normal application question, so only a
    # bare "Username" field counts as a sign-in
    BARE_LABELS = ("username", "user name", "login", "log in", "sign in", "user id")
    CODE_PATTERN = re.compile(
        r"verification code|one time (pass)?code|security code|\b2fa\b|\bmfa\b|\botp\b")

    def matches(self, page_field: PageField) -> bool:
        """Return True for a sign-in name or a one-time code box."""
        if page_field.autocomplete.lower() in ("username", "one-time-code"):
            return True
        if page_field.bare_label() in self.BARE_LABELS:
            return True
        return bool(self.CODE_PATTERN.search(page_field.text()))
