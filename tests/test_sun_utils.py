import pytest

from lib.sun_utils import get_daylight_utc_hours


class TestGetDaylightUtcHours:

    def test_los_angeles_summer(self):
        """LA in June: sunrise ~12:45 UTC, sunset ~3:08 UTC (wrapping)."""
        result = get_daylight_utc_hours(33.95, -118.45, 6)
        assert result is not None
        assert 12.0 < result['sunrise'] < 14.5
        assert 2.0 < result['sunset'] < 4.5
        # Wrapping case: sunrise > sunset in UTC
        assert result['sunrise'] > result['sunset']

    def test_los_angeles_winter(self):
        """LA in December: sunrise ~14:55 UTC, sunset ~0:48 UTC (wrapping)."""
        result = get_daylight_utc_hours(33.95, -118.45, 12)
        assert result is not None
        assert 14.0 < result['sunrise'] < 16.0
        assert 0.0 < result['sunset'] < 2.0
        assert result['sunrise'] > result['sunset']

    def test_london_summer(self):
        """London in June: sunrise ~3:45 UTC, sunset ~20:15 UTC (non-wrapping)."""
        result = get_daylight_utc_hours(51.47, -0.46, 6)
        assert result is not None
        assert result['sunrise'] < result['sunset']
        assert 3.0 < result['sunrise'] < 5.0
        assert 19.0 < result['sunset'] < 22.0

    def test_tokyo_winter(self):
        """Tokyo in December: sunrise ~21:45 UTC, sunset ~7:30 UTC (wrapping)."""
        result = get_daylight_utc_hours(35.68, 139.77, 12)
        assert result is not None
        assert result['sunrise'] > result['sunset']

    def test_none_lat(self):
        assert get_daylight_utc_hours(None, -118.0, 6) is None

    def test_none_lon(self):
        assert get_daylight_utc_hours(33.95, None, 6) is None

    def test_polar_region(self):
        """Above Arctic Circle in June (midnight sun) — should not crash."""
        result = get_daylight_utc_hours(71.0, 25.0, 6)
        # astral raises ValueError for polar day; function returns None
        assert result is None or ('sunrise' in result and 'sunset' in result)

    def test_return_types(self):
        result = get_daylight_utc_hours(33.95, -118.45, 6)
        assert isinstance(result['sunrise'], float)
        assert isinstance(result['sunset'], float)
        assert 0.0 <= result['sunrise'] <= 24.0
        assert 0.0 <= result['sunset'] <= 24.0
