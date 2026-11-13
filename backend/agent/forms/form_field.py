"""One question on an application form, and the answer the agent picked for it."""
from dataclasses import dataclass, field


@dataclass
class FormField:
    """A question on the form, the same shape for every site."""

    key: str  # how the site's form class finds it on the page
    label: str
    kind: str  # text, textarea, select, multi_select, location, school, date or file
    required: bool = False
    options: list[str] = field(default_factory=list)
    profile_key: str = ""  # set when the answer comes straight from the profile, like "email"


@dataclass
class FieldAnswer:
    """What the agent will put in a field, and where it came from."""

    value: str
    source: str  # profile, saved or claude
    confidence: int = 100
    reason: str = ""
