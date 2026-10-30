"""Protected fields (US8, F8, SE2).

The agent never types into a CAPTCHA, a password or sign-in box, or a Social
Security number field. When a form has one, the application goes to Needs you
and the student finishes that step on the employer's site.

How the rest of the agent uses this:

- scan_page(page) once the posting loads, to hand the whole form off early.
- check_field(field) right before typing into any single field, as a last guard
  for fields that only show up partway through (page 2 of a form, say).

Only a field's attributes are read (label, name, id, type, autocomplete,
placeholder), never what's typed in it, so an SSN can't reach our logs or
database through this check.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Handoff kinds, also the words the UI can switch on.
CAPTCHA = "captcha"
SSN = "ssn"
PASSWORD = "password"
LOGIN = "login"


@dataclass(frozen=True)
class FormField:
    """What the agent can see about one input before filling it."""

    label: str = ""
    name: str = ""
    element_id: str = ""
    input_type: str = "text"
    autocomplete: str = ""
    placeholder: str = ""

    def text(self) -> str:
        """All the descriptive attributes as one lowercase string, for keyword checks.

        Underscores and dashes become spaces so social_security_number and
        social-security-number read the same as the label "Social Security number".
        """
        joined = " ".join([self.label, self.name, self.element_id, self.placeholder])
        return re.sub(r"[_\-]+", " ", joined).lower()


@dataclass(frozen=True)
class Handoff:
    """One step the student has to do themselves, and why."""

    kind: str
    field_label: str
    message: str


class ProtectedCheck(ABC):
    """One kind of field the agent must never fill."""

    kind = ""
    message = ""

    @abstractmethod
    def matches(self, field: FormField) -> bool:
        """True if the agent must not type into this field."""

    def handoff(self, field: FormField) -> Handoff:
        return Handoff(self.kind, field.label or field.name, self.message)


class CaptchaCheck(ProtectedCheck):
    """reCAPTCHA, hCaptcha and Cloudflare Turnstile.

    These usually live in an iframe, so scan_page also checks frame URLs. The
    hidden response fields they add to the form are caught here too.
    """

    kind = CAPTCHA
    message = ("This form has a CAPTCHA, and the agent never solves those. "
               "Open the form to finish it yourself.")

    FRAME_HOSTS = ("google.com/recaptcha", "recaptcha.net", "hcaptcha.com",
                   "challenges.cloudflare.com")

    def matches(self, field: FormField) -> bool:
        return "captcha" in field.text() or "turnstile" in field.text()

    def matches_frame_url(self, url: str) -> bool:
        return any(host in url.lower() for host in self.FRAME_HOSTS)


class SsnCheck(ProtectedCheck):
    """Social Security numbers. We never fill or store these (SE2)."""

    kind = SSN
    message = ("This form asks for a Social Security number. We never fill or store "
               "SSNs, so finish this one on the employer's site.")

    PATTERN = re.compile(r"\bssn\b|social security|social insurance number|\bsin number\b")

    def matches(self, field: FormField) -> bool:
        return bool(self.PATTERN.search(field.text()))


class PasswordCheck(ProtectedCheck):
    """Any password box, which also means the form wants an account."""

    kind = PASSWORD
    message = ("This form wants a password or an account. Sign in on the employer's "
               "site yourself, then finish the application there.")

    def matches(self, field: FormField) -> bool:
        return (field.input_type.lower() == "password"
                or field.autocomplete.lower() in ("current-password", "new-password"))


class LoginCheck(ProtectedCheck):
    """Sign-in and verification steps other than the password box itself.

    Kept narrow on purpose: a question like "GitHub username" is a normal
    application question, so only a bare "Username" field counts as a login.
    """

    kind = LOGIN
    message = ("This form needs a sign-in or a verification code. Finish that step "
               "on the employer's site.")

    BARE_LOGIN_LABELS = ("username", "user name", "login", "log in", "sign in", "user id")
    CODE_PATTERN = re.compile(
        r"verification code|one time (pass)?code|security code|\b2fa\b|\bmfa\b|\botp\b")

    def matches(self, field: FormField) -> bool:
        if field.autocomplete.lower() in ("username", "one-time-code"):
            return True
        if field.label.strip().lower().rstrip("*: ") in self.BARE_LOGIN_LABELS:
            return True
        return bool(self.CODE_PATTERN.search(field.text()))


# Reads attributes only. Never read .value here (SE2).
COLLECT_FIELDS_JS = """
() => Array.from(document.querySelectorAll('input, textarea, select')).map((el) => {
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
    """Finds every step on a form that has to go to the student."""

    def __init__(self, checks: list[ProtectedCheck] | None = None):
        self.checks = checks if checks is not None else [
            CaptchaCheck(), SsnCheck(), PasswordCheck(), LoginCheck()]

    def check_field(self, field: FormField) -> Handoff | None:
        """The handoff for this field, or None if the agent may fill it."""
        for check in self.checks:
            if check.matches(field):
                return check.handoff(field)
        return None

    def scan_fields(self, fields: list[FormField]) -> list[Handoff]:
        return [h for h in (self.check_field(f) for f in fields) if h is not None]

    def scan_page(self, page) -> list[Handoff]:
        """Check every field on a loaded Playwright page, plus CAPTCHA iframes."""
        fields = [FormField(**raw) for raw in page.evaluate(COLLECT_FIELDS_JS)]
        handoffs = self.scan_fields(fields)
        for check in self.checks:
            if isinstance(check, CaptchaCheck) and any(
                    check.matches_frame_url(frame.url) for frame in page.frames):
                handoffs.append(Handoff(CAPTCHA, "CAPTCHA", check.message))
        return handoffs


def needs_you_reason(handoffs: list[Handoff]) -> str:
    """One plain-language reason for the Needs you list, one sentence per kind."""
    seen = []
    for handoff in handoffs:
        if handoff.message not in seen:
            seen.append(handoff.message)
    return " ".join(seen)
