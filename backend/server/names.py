"""A person's name as the profile stores it: firstName, middleName (optional), lastName.

`split_name("Mary Ann Smith")` -> ("Mary", "Ann", "Smith"). Used by the resume import (which
finds one name line) and by the migration of profiles saved with a single `name`.
"""

NAME_KEYS = ("firstName", "middleName", "lastName")

# Kept with the last name: "Martin Luther King Jr." -> last "King Jr.".
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "phd", "md"}
# Lowercase particles start the last name: "Ludwig van Beethoven" -> last "van Beethoven".
_PARTICLES = {"van", "von", "de", "del", "della", "der", "di", "da", "du", "la", "le", "st",
              "bin", "ibn"}


def split_name(full: str) -> tuple[str, str, str]:
    """(first, middle, last). One word is a first name; middle is "" for two-word names and
    holds every word between the first and the last name for longer ones."""
    words = (full or "").split()
    if not words:
        return "", "", ""
    if len(words) == 1:
        return words[0], "", ""
    first, rest = words[0], words[1:]
    last_start = len(rest) - 1
    while last_start > 0 and rest[last_start].strip(".,").lower() in _SUFFIXES:
        last_start -= 1
    while last_start > 0 and rest[last_start - 1].lower() in _PARTICLES:
        last_start -= 1
    return first, " ".join(rest[:last_start]), " ".join(rest[last_start:])


def full_name(profile: dict) -> str:
    """"First Middle Last", skipping empty parts."""
    return " ".join(" ".join(str(profile.get(key) or "").split())
                    for key in NAME_KEYS if str(profile.get(key) or "").strip())


def migrate_profile(profile: dict) -> dict:
    """A profile saved before the name was split: its `name` becomes the three name fields.

    A stored name field, even an empty one, wins over the legacy `name`, which is dropped.
    """
    if "name" not in profile:
        return profile
    migrated = {k: v for k, v in profile.items() if k != "name"}
    if not any(key in profile for key in NAME_KEYS):
        first, middle, last = split_name(str(profile.get("name") or ""))
        migrated.update(firstName=first, middleName=middle, lastName=last)
    return migrated
