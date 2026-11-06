"""What every site's form class has to be able to do."""
from abc import ABC, abstractmethod


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

    def wait_until_ready(self, page):
        """Wait until the form is on the page."""
        page.wait_for_load_state()

    @abstractmethod
    def fill(self, page, form_field, value):
        """Put one answer into the form. File fields get a file path."""

    @abstractmethod
    def submit(self, page):
        """Press the form's submit button."""

    @abstractmethod
    def is_confirmed(self, page):
        """Return True once the site shows that the application went through."""
