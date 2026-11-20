"""Reads the dates people and Claude write ("June 2027", "6/1/2027", "ASAP")."""
import re
from calendar import month_name
from datetime import date

# Words that mean "as soon as possible", which is today for a start date
RIGHT_AWAY = re.compile(r"^(today|now|immediately|right away|asap|as soon as possible)$")
ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b")
YEAR = re.compile(r"\b(\d{4})\b")
NUMERIC_MONTH = re.compile(r"\b(\d{1,2})\s*[/-]\s*\d{4}\b|\b\d{4}\s*[/-]\s*(\d{1,2})\b")


def month_number(word: str) -> int:
    """Return 1-12 for a month name or its short form ("Jun", "Sept."), or 0."""
    word = word.rstrip(".").lower()
    if len(word) < 3:
        return 0
    return next((number for number in range(1, 13)
                 if month_name[number].lower().startswith(word)
                 or (word == "sept" and number == 9)), 0)


# Each written form a date can take, and how its parts map to (year, month, day). US forms
# write the month first, and a date with no day means the first of the month.
DATE_FORMS = [
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda year, month, day: (year, month, day)),
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", lambda month, day, year: (year, month, day)),
    (r"(\d{1,2})/(\d{4})", lambda month, year: (year, month, "1")),
    (r"([a-z.]+) (\d{1,2}) (\d{4})", lambda month, day, year: (year, month_number(month), day)),
    (r"(\d{1,2}) ([a-z.]+) (\d{4})", lambda day, month, year: (year, month_number(month), day)),
    (r"([a-z.]+) (\d{4})", lambda month, year: (year, month_number(month), "1")),
]


def parse_date(text: str, today: date | None = None) -> date | None:
    """Return the date the text names (words like "ASAP" mean today), or None."""
    words = " ".join(ORDINAL.sub("", text.lower().replace(",", " ")).split()).rstrip(".!")
    if RIGHT_AWAY.match(words):
        return today or date.today()
    for pattern, order in DATE_FORMS:
        found = re.fullmatch(pattern, words)
        if found:
            year, month, day = order(*found.groups())
            try:
                return date(int(year), int(month), int(day))
            except ValueError:
                return None  # a month or day that doesn't exist, like 13/40/2027
    return None


def iso_date(text: str, today: date | None = None) -> str:
    """Return the text as YYYY-MM-DD, or "" if it isn't a date."""
    found = parse_date(text, today)
    return found.isoformat() if found else ""


def month_and_year(text: str) -> tuple[str, str]:
    """Split "May 2027", "Aug. 2023" or "05/2027" into ("May", "2027"), "" for a missing part."""
    year = YEAR.search(text)
    month = ""
    for number in range(1, 13):
        if re.search(rf"\b{month_name[number][:3]}", text, re.IGNORECASE):
            month = month_name[number]
            break
    numeric = NUMERIC_MONTH.search(text)
    if not month and numeric and 1 <= int(numeric.group(1) or numeric.group(2)) <= 12:
        month = month_name[int(numeric.group(1) or numeric.group(2))]
    return month, year.group(1) if year else ""
