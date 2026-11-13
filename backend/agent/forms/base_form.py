"""What every site's form class has to be able to do."""
from abc import ABC, abstractmethod


class PostingClosed(OSError):
    """The site has no open posting at that link (taken down, or never existed)."""


class AtsForm(ABC):
    """An application form on one applicant tracking system (Greenhouse, Lever or Ashby)."""

    def __init__(self, link):
        self.link = link

    @abstractmethod
    def form_url(self):
        """Return the page Playwright opens to fill the form."""

    @abstractmethod
    def read_fields(self):
        """Return the form's questions as a list of FormField."""

    def posting(self):
        """Return the company, job title and location read with the form ("" when unknown)."""
        return {"company": "", "title": "", "location": ""}

    def wait_until_ready(self, page):
        """Wait until the form is on the page."""
        page.wait_for_load_state()

    def shows(self, page, form_field):  # pylint: disable=unused-argument
        """Return False to skip a field this page doesn't have (it was only a maybe)."""
        return True

    @abstractmethod
    def fill(self, page, form_field, value):
        """Put one answer into the form. File fields get a file path.

        Returns what the form now shows when that differs from the value (like "Other" for a
        school that isn't on the site's list), or None.
        """

    @abstractmethod
    def submit(self, page):
        """Press the form's submit button."""

    @abstractmethod
    def is_confirmed(self, page, timeout_ms=None):
        """Return True once the site shows that the application went through.

        Waits up to timeout_ms for it (the page's default timeout when None).
        """

    def is_open(self, page):  # pylint: disable=unused-argument
        """Return True while the filled-in form is still on the page."""
        return True

    def asks_for_code(self, page):  # pylint: disable=unused-argument
        """Return True if the site is asking for a code it emailed (a human check)."""
        return False

    def enter_code(self, page, code):
        """Type the code the site emailed into its prompt and send it (press its button)."""
        raise NotImplementedError(f"{type(self).__name__} can't enter an emailed code")

    def code_rejected(self, page):  # pylint: disable=unused-argument
        """Return True if the page says the code typed into its prompt was wrong or expired."""
        return False
