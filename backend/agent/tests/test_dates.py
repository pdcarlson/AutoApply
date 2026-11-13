"""Tests for reading the dates people and Claude write."""
from datetime import date

import pytest

from agent.forms.dates import iso_date, parse_date

TODAY = date(2026, 11, 12)


@pytest.mark.parametrize("text, expected", [
    ("2027-06-01", date(2027, 6, 1)),
    ("6/1/2027", date(2027, 6, 1)),
    ("06/01/2027", date(2027, 6, 1)),
    ("June 1, 2027", date(2027, 6, 1)),
    ("Jun 1st 2027.", date(2027, 6, 1)),
    ("1 June 2027", date(2027, 6, 1)),
    ("June 2027", date(2027, 6, 1)),
    ("Sept. 2027", date(2027, 9, 1)),
    ("06/2027", date(2027, 6, 1)),
    ("ASAP", TODAY),
    ("Immediately", TODAY),
    ("13/40/2027", None),
    ("Ju 2027", None),
    ("whenever works", None),
    ("", None),
])
def test_parse_date(text, expected):
    """Month-first numbers, month names, a month alone and "ASAP" are dates; nonsense isn't."""
    assert parse_date(text, today=TODAY) == expected


def test_iso_date():
    """Dates come back as YYYY-MM-DD, and anything else as an empty string."""
    assert iso_date("June 2027") == "2027-06-01"
    assert iso_date("not sure") == ""
