"""One question on an application form, and the answer the agent picked for it."""
from dataclasses import dataclass, field
from enum import StrEnum


class FieldKind(StrEnum):
    """What sort of box a form question is."""

    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    LOCATION = "location"
    SCHOOL = "school"
    DATE = "date"
    FILE = "file"


class AnswerSource(StrEnum):
    """Where the agent found an answer."""

    PROFILE = "profile"
    SAVED = "saved"
    CLAUDE = "claude"


@dataclass
class FormField:
    """A question on the form, the same shape for every site."""

    key: str  # how the site's form class finds it on the page
    label: str
    kind: FieldKind
    required: bool = False
    options: list[str] = field(default_factory=list)
    profile_key: str = ""  # set when the answer comes straight from the profile, like "email"

    def __post_init__(self):
        """Accept the kind as plain text too, as stored JSON gives it."""
        self.kind = FieldKind(self.kind)


@dataclass
class FieldAnswer:
    """What the agent will put in a field, and where it came from."""

    value: str
    source: AnswerSource
    confidence: int = 100
    reason: str = ""

    def __post_init__(self):
        """Accept the source as plain text too, as stored JSON gives it."""
        self.source = AnswerSource(self.source)
