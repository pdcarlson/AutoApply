"""Picks answers from the dropdowns and search-as-you-type lists that forms show."""
import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

# What the school box offers for a school that isn't on Greenhouse's list
OTHER_SCHOOL = "Other"
# How long to wait for the school to show up in the box's search before picking Other
SCHOOL_WAIT_MS = 5000

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def choose_option(page, value: str) -> None:
    """Click the open dropdown's option that matches the value exactly, or else starts with it."""
    page.get_by_role("option").first.wait_for()
    exact = page.get_by_role("option", name=value, exact=True)
    if exact.count():
        exact.first.click()
    else:
        # Some options add extra text, like "United States +1" in the phone country list
        starts = re.compile("^" + re.escape(value), re.IGNORECASE)
        page.get_by_role("option").filter(has_text=starts).first.click()


def choose_location(page, value: str) -> None:
    """Click the city suggestion for a "City, State" value, or raise if none matches.

    Suggestions read like "Mechanicville, New York, United States", so a state written as "NY"
    is matched by its full name. A same-named city in another state is never picked, so the
    run stops instead of sending a wrong location.
    """
    page.get_by_role("option").first.wait_for()
    city, _, state = (part.strip() for part in value.partition(","))
    states = {state.lower(), US_STATES.get(state.upper(), state).lower()} - {""}
    options = page.get_by_role("option")
    seen = []
    for index in range(options.count()):
        text = options.nth(index).inner_text()
        seen.append(text)
        parts = [part.strip().lower() for part in text.split(",")]
        if parts[0] == city.lower() and (not states or (len(parts) > 1 and parts[1] in states)):
            options.nth(index).click()
            return
    raise PlaywrightError(f'No location suggestion matches "{value}". Suggestions: {seen}')


def _menu_option(page, text: str):
    """Return the open dropdown's option named exactly `text`, ignoring case and extra spaces."""
    words = r"\s+".join(re.escape(word) for word in text.split())
    return page.locator(".select__menu").get_by_role(
        "option", name=re.compile(f"^{words}$", re.IGNORECASE)).first


def _pick_searched(page, box, text: str) -> bool:
    """Type into a search-as-you-type list and click the option named text, or return False."""
    # The list sometimes comes back empty the first time it's asked, so the search is typed twice
    for _attempt in range(2):
        box.click()
        box.fill(text)
        try:
            _menu_option(page, text).click(timeout=SCHOOL_WAIT_MS)
            return True
        except PlaywrightTimeout:
            box.fill("")
    return False


def choose_school(page, box, school: str) -> str | None:
    """Pick the school from Greenhouse's list, or "Other" if it isn't there.

    Returns "Other" when it picked that, else None.
    """
    if _pick_searched(page, box, school):
        return None
    if _pick_searched(page, box, OTHER_SCHOOL):
        return OTHER_SCHOOL
    raise PlaywrightError(f'The school list showed neither "{school}" nor "{OTHER_SCHOOL}".')
