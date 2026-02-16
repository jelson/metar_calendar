"""Timezone utilities for computing UTC offsets applicable to a given month."""

import calendar
from datetime import datetime
from zoneinfo import ZoneInfo


def get_utc_offsets_for_month(tz_name, month):
    """Return the distinct UTC offsets active during the given month.

    Checks the 1st and last day of the month to detect DST transitions.
    At most one DST transition can occur per month, so two samples suffice.

    Args:
        tz_name: IANA timezone string (e.g., "America/Los_Angeles"), or None
        month: Month number (1-12)

    Returns:
        List of dicts with 'abbr' (str) and 'utc_offset_hours' (float),
        sorted descending by utc_offset_hours (closest to UTC first).
        Returns [] if tz_name is None, empty, or invalid.
    """
    if not tz_name:
        return []

    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, Exception):
        return []

    year = datetime.now().year
    last_day = calendar.monthrange(year, month)[1]

    # Sample midnight on day 1 and noon on last day. Using midnight on day 1
    # catches the pre-transition state if a DST transition happens on the 1st
    # (e.g., US "fall back" on Nov 1, 2026 at 2 AM — midnight is still PDT).
    samples = [
        datetime(year, month, 1, 0, 0, 0, tzinfo=tz),
        datetime(year, month, last_day, 12, 0, 0, tzinfo=tz),
    ]

    offsets = {}
    for dt in samples:
        abbr = dt.tzname()
        offset_hours = dt.utcoffset().total_seconds() / 3600
        if abbr not in offsets:
            offsets[abbr] = offset_hours

    result = [
        {"abbr": abbr, "utc_offset_hours": hours}
        for abbr, hours in offsets.items()
    ]
    result.sort(key=lambda x: -x["utc_offset_hours"])
    return result
