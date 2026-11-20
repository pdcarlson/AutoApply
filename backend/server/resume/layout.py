"""Splits a resume layout line into its text, date and place columns."""
from server.resume.dates import RANGE_RE, cut_dates, has_dates
from server.resume.line_text import clean
from server.resume.patterns import COLUMNS_RE
from server.resume.places import find_location


def split_columns(line: str) -> list[str]:
    """Return the line's columns: the text between gaps of three or more spaces."""
    return [column for column in COLUMNS_RE.split(line.strip()) if column]


def split_line(line: str) -> tuple[str, str, str]:
    """Split a layout line into (text, dates text, location).

    A right-hand (or left-hand) date column is the dates and a column that is only a place is
    the location. Otherwise a date range inside the text is cut out of it.
    """
    columns = split_columns(line)
    dates = ""
    location = ""
    if len(columns) > 1 and has_dates(columns[-1]):
        # a date column can carry more: "Computer Science, Colorado School of Mines (2014–2018)"
        dates, rest = cut_dates(columns.pop())
        if rest:
            columns.append(rest)
    elif len(columns) > 1 and has_dates(columns[0]) and not cut_dates(columns[0])[1]:
        dates = columns.pop(0)
    if len(columns) > 1 and _is_place_column(columns[-1]):
        location = columns.pop()
    text = ", ".join(columns)
    if not dates:
        found_range = RANGE_RE.search(text)
        if found_range:
            dates = found_range.group(0)
            text = clean(text[:found_range.start()] + " " + text[found_range.end():])
    return clean(text), dates, location


def _is_place_column(column: str) -> bool:
    """Return True when the whole column is "City, ST"."""
    found = find_location(column)
    return bool(found) and found[0] == column.split(",")[0]
