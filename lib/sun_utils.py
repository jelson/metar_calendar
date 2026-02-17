"""Sun position utilities for computing sunrise/sunset times."""

from datetime import datetime

from astral import LocationInfo
from astral.sun import sun


def get_daylight_utc_hours(lat, lon, month):
    """Compute sunrise and sunset as UTC fractional hours for the 15th of the given month.

    Args:
        lat: Latitude in decimal degrees (positive = north)
        lon: Longitude in decimal degrees (positive = east)
        month: Month number (1-12)

    Returns:
        Dict with 'sunrise' and 'sunset' as float UTC hours (0.0-24.0),
        or None if lat/lon is missing or sun doesn't rise/set (polar regions).
    """
    if lat is None or lon is None:
        return None

    try:
        location = LocationInfo(latitude=lat, longitude=lon)
        dt = datetime(datetime.now().year, month, 15)
        s = sun(location.observer, date=dt)

        def to_fractional_hours(dt):
            return dt.hour + dt.minute / 60 + dt.second / 3600

        return {
            'sunrise': round(to_fractional_hours(s['sunrise']), 2),
            'sunset': round(to_fractional_hours(s['sunset']), 2),
        }
    except (ValueError, AttributeError):
        # astral raises ValueError for polar day/night
        return None
