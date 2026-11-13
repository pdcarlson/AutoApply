"""Reads the dates people and Claude write ("June 2027", "6/1/2027", "ASAP") for date questions.

Date answers are kept as YYYY-MM-DD, and each site's form types them the way its picker wants.
"""
import re
from calendar import month_name
from datetime import date

# Words that mean "as soon as possible", which is today for a start date
RIGHT_AWAY = re.compile(r"^(today|now|immediately|right away|asap|as soon as possible)$")
ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b")


def month_number(word):
    """Return 1-12 for a month name or its short form ("Jun", "Sept."), or 0."""
    word = word.rstrip(".").lower()
    if len(word) < 3:
        return 0
    return next((number for number in range(1, 13)
                 if month_name[number].lower().startswith(word)
                 or (word == "sept" and number == 9)), 0)


def parse_date(text, today=None):
    """Return the date the text names, or None if it doesn't name one.

    Reads 2027-06-01, 6/1/2027 (month first, as on US forms), June 1, 2027, 1 June 2027 and
    June 2027 (the first of the month). Words like "ASAP" or "immediately" mean today.
    """
    words = " ".join(ORDINAL.sub("", text.lower().replace(",", " ")).split()).rstrip(".!")
    if RIGHT_AWAY.match(words):
        return today or date.today()
    patterns = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda y, m, d: (y, m, d)),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", lambda m, d, y: (y, m, d)),
        (r"(\d{1,2})/(\d{4})", lambda m, y: (y, m, "1")),
        (r"([a-z.]+) (\d{1,2}) (\d{4})", lambda m, d, y: (y, month_number(m), d)),
        (r"(\d{1,2}) ([a-z.]+) (\d{4})", lambda d, m, y: (y, month_number(m), d)),
        (r"([a-z.]+) (\d{4})", lambda m, y: (y, month_number(m), "1")),
    ]
    for pattern, order in patterns:
        found = re.fullmatch(pattern, words)
        if found:
            year, month, day = order(*found.groups())
            try:
                return date(int(year), int(month), int(day))
            except ValueError:
                return None  # a month or day that doesn't exist, like 13/40/2027
    return None


def iso_date(text, today=None):
    """Return the text as YYYY-MM-DD, or "" if it isn't a date."""
    found = parse_date(text, today)
    return found.isoformat() if found else ""
