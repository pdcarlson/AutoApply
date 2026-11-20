"""What every site's form class has to be able to do."""
from abc import ABC, abstractmethod

from agent.forms.form_field import FormField
from agent.jobs.job_link import JobLink


class PostingClosed(OSError):
    """The site has no open posting at that link (taken down, or never existed)."""


class CodeEntryUnsupported(NotImplementedError):
    """This site's form can't type in a code the site emailed."""


class AtsForm(ABC):
    """An application form on one applicant tracking system (Greenhouse, Lever or Ashby)."""

    def __init__(self, link: JobLink):
        """Store the job link this form belongs to."""
        self.link = link

    @abstractmethod
    def form_url(self) -> str:
        """Return the page Playwright opens to fill the form."""

    @abstractmethod
    def read_fields(self) -> list[FormField]:
        """Return the form's questions."""

    def posting(self) -> dict:
        """Return the company, job title and location read with the form ("" when unknown)."""
        return {"company": "", "title": "", "location": ""}

    def wait_until_ready(self, page) -> None:
        """Wait until the form is on the page."""
        page.wait_for_load_state()

    def shows(self, page, form_field: FormField) -> bool:  # pylint: disable=unused-argument
        """Return False to skip a field this page doesn't have (it was only a maybe)."""
        # The base form shows every field; sites whose fields vary override this with the page
        return True

    @abstractmethod
    def fill(self, page, form_field: FormField, value: str) -> str | None:
        """Put one answer into the form (a file path for file fields).

        Returns what the form now shows when that differs from the value (like "Other" for a
        school that isn't on the site's list), or None.
        """

    @abstractmethod
    def submit(self, page) -> None:
        """Press the form's submit button."""

    @abstractmethod
    def is_confirmed(self, page, timeout_ms: float | None = None) -> bool:
        """Return True once the site shows the application went through, waiting up to timeout_ms.

        None waits for the page's default timeout.
        """

    def is_open(self, page) -> bool:  # pylint: disable=unused-argument  # overrides use it
        """Return True while the filled-in form is still on the page."""
        return True

    def asks_for_code(self, page) -> bool:  # pylint: disable=unused-argument  # overrides use it
        """Return True if the site is asking for a code it emailed (a human check)."""
        return False

    def enter_code(self, page, code: str) -> None:
        """Type the code the site emailed into its prompt and send it (press its button)."""
        raise CodeEntryUnsupported(f"{type(self).__name__} can't enter an emailed code")

    def code_rejected(self, page) -> bool:  # pylint: disable=unused-argument  # overrides use it
        """Return True if the page says the code typed into its prompt was wrong or expired."""
        return False
