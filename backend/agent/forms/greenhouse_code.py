"""The verification code prompt Greenhouse sometimes shows after Submit."""
import re

from playwright.sync_api import Error as PlaywrightError

# The prompt reads like "A verification code was sent to ... Enter the 8-character code to
# confirm you're a human."
CODE_PROMPT = re.compile(r"verification code|enter the \d+-character code", re.IGNORECASE)
# The code goes into one box per character (security-input-0, -1, ...), then Submit application
# is pressed again. A single code box with a Verify button is handled too.
CODE_BOXES = "input[id^='security-input-']"
CODE_BOX = re.compile(r"security code|verification code|^code$", re.IGNORECASE)
CODE_BUTTONS = (re.compile(r"verify|confirm", re.IGNORECASE), re.compile("submit", re.IGNORECASE))
CODE_ERROR = re.compile(r"(incorrect|invalid|expired|wrong)[^.]{0,30}(security|verification) code"
                        r"|(security|verification) code[^.]{0,30}(incorrect|invalid|expired|wrong"
                        r"|not valid|doesn.t match)", re.IGNORECASE)


class GreenhouseCodePrompt:
    """Reads and answers Greenhouse's emailed-code check on an open page."""

    def __init__(self, page):
        """Store the page that shows the code prompt."""
        self.page = page

    def is_showing(self) -> bool:
        """Return True if Greenhouse is asking for the verification code it emailed."""
        try:
            return self.page.get_by_text(CODE_PROMPT).first.is_visible()
        except PlaywrightError:
            return False

    def enter(self, code: str) -> None:
        """Type the emailed code into Greenhouse's code boxes and send it."""
        boxes = self.page.locator(CODE_BOXES)
        if boxes.count() > 1:
            for index in range(boxes.count()):
                boxes.nth(index).fill(code[index] if index < len(code) else "")
        else:
            box = self.page.get_by_label(CODE_BOX)
            if box.count() == 0:
                box = self.page.locator(CODE_BOXES)
            box.first.fill(code)
        for name in CODE_BUTTONS:
            button = self.page.get_by_role("button", name=name)
            if button.count() and button.first.is_visible():
                button.first.click()
                return
        raise PlaywrightError("Couldn't find the button that sends the code.")

    def is_rejected(self) -> bool:
        """Return True if Greenhouse says the code was wrong or expired."""
        try:
            return self.page.get_by_text(CODE_ERROR).first.is_visible()
        except PlaywrightError:
            return False
