"""Finds the protected steps on a form, from its questions or the open page."""
from playwright.sync_api import Error as PlaywrightError

from agent.forms.form_field import FormField
from agent.forms.protected.checks import (CaptchaCheck, LoginCheck, PageField, PasswordCheck,
                                          ProtectedCheck, SsnCheck)
from agent.forms.protected.handoff import Handoff, HandoffKind

MIN_CAPTCHA_PX = 30  # smaller frames are a CAPTCHA's hidden helpers, not something to solve

# Reads what describes each visible field, never its value, so an SSN or a password can't
# reach the logs or the saved data
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

    def __init__(self, checks: list[ProtectedCheck] | None = None):
        """Use the given checks, or every built-in check (CAPTCHA, SSN, password, sign-in)."""
        self.checks = checks if checks is not None else [
            CaptchaCheck(), SsnCheck(), PasswordCheck(), LoginCheck()]

    def check_field(self, page_field: PageField) -> Handoff | None:
        """Return the Handoff for this field, or None if the agent may fill it."""
        for check in self.checks:
            if check.matches(page_field):
                return check.handoff(page_field)
        return None

    def check_question(self, form_field: FormField) -> Handoff | None:
        """Return the Handoff for a FormField read from the site, or None."""
        return self.check_field(PageField(label=form_field.label, name=form_field.key))

    def scan_page(self, page) -> list[Handoff]:
        """Return a Handoff for every protected field and CAPTCHA showing on the open page."""
        fields = [PageField(**described) for described in page.evaluate(VISIBLE_FIELDS_JS)]
        handoffs = [found for found in map(self.check_field, fields) if found is not None]
        return handoffs + self.scan_captchas(page)

    def scan_captchas(self, page) -> list[Handoff]:
        """Return a Handoff if a CAPTCHA is showing on the open page, else []."""
        for check in self.checks:
            if isinstance(check, CaptchaCheck) and any(
                    check.matches_frame(frame.url) and frame_shows(frame)
                    for frame in page.frames):
                return [Handoff(HandoffKind.CAPTCHA, "CAPTCHA", check.message)]
        return []


def frame_shows(frame) -> bool:
    """Return True if the frame is on screen and big enough to hold something to solve."""
    try:
        element = frame.frame_element()
        box = element.bounding_box() if element.is_visible() else None
    except PlaywrightError:
        return False
    return bool(box) and box["width"] >= MIN_CAPTCHA_PX and box["height"] >= MIN_CAPTCHA_PX
