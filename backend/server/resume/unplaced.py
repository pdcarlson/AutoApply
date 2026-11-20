"""Moves an accepted unplaced resume section into the profile."""
import re

from server.resume.found_entries import COURSEWORK_SUGGESTION, CUSTOM_SUGGESTION
from server.resume.line_text import split_label


def accept_unplaced(profile: dict, section: dict) -> None:
    """Add the section's text where its suggestion says: coursework or a custom field."""
    suggestion = section.get("suggestion")
    label, text = split_label(section.get("text") or "")
    if suggestion == COURSEWORK_SUGGESTION and profile.get("education"):
        school = profile["education"][0]
        school["coursework"] = ", ".join(filter(None, [(school.get("coursework") or "").strip(),
                                                       text.strip()]))
        return
    if suggestion in (COURSEWORK_SUGGESTION, CUSTOM_SUGGESTION):
        custom = profile.setdefault("custom", [])
        custom.append({"id": _next_id("cf", custom), "label": label or "From your resume",
                       "value": text})


def _next_id(prefix: str, items: list[dict]) -> str:
    """Return `<prefix>-<n>` with n one more than the highest such id in `items`."""
    numbers = [int(match.group(1)) for item in items
               if (match := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", str(item.get("id", ""))))]
    return f"{prefix}-{max(numbers, default=0) + 1}"
