import pytest

from lib.timezone_utils import get_utc_offsets_for_month


class TestGetUtcOffsetsForMonth:

    def test_single_offset_winter(self):
        """US Pacific in January - PST only."""
        result = get_utc_offsets_for_month("America/Los_Angeles", 1)
        assert len(result) == 1
        assert result[0]["abbr"] == "PST"
        assert result[0]["utc_offset_hours"] == -8.0

    def test_single_offset_summer(self):
        """US Pacific in July - PDT only."""
        result = get_utc_offsets_for_month("America/Los_Angeles", 7)
        assert len(result) == 1
        assert result[0]["abbr"] == "PDT"
        assert result[0]["utc_offset_hours"] == -7.0

    def test_dst_transition_march(self):
        """US Pacific in March - spring forward, both PST and PDT."""
        result = get_utc_offsets_for_month("America/Los_Angeles", 3)
        assert len(result) == 2
        # Sorted descending: PDT (-7) before PST (-8)
        assert result[0]["abbr"] == "PDT"
        assert result[0]["utc_offset_hours"] == -7.0
        assert result[1]["abbr"] == "PST"
        assert result[1]["utc_offset_hours"] == -8.0

    def test_dst_transition_november(self):
        """US Pacific in November - fall back, both PDT and PST."""
        result = get_utc_offsets_for_month("America/Los_Angeles", 11)
        assert len(result) == 2
        assert result[0]["abbr"] == "PDT"
        assert result[0]["utc_offset_hours"] == -7.0
        assert result[1]["abbr"] == "PST"
        assert result[1]["utc_offset_hours"] == -8.0

    def test_us_eastern_summer(self):
        """US Eastern in June - EDT only."""
        result = get_utc_offsets_for_month("America/New_York", 6)
        assert len(result) == 1
        assert result[0]["abbr"] == "EDT"
        assert result[0]["utc_offset_hours"] == -4.0

    def test_utc(self):
        """UTC - always one offset at 0."""
        result = get_utc_offsets_for_month("UTC", 6)
        assert len(result) == 1
        assert result[0]["utc_offset_hours"] == 0.0

    def test_no_dst_timezone(self):
        """Arizona (no DST) - MST for all 12 months."""
        for month in range(1, 13):
            result = get_utc_offsets_for_month("America/Phoenix", month)
            assert len(result) == 1
            assert result[0]["abbr"] == "MST"
            assert result[0]["utc_offset_hours"] == -7.0

    def test_half_hour_offset(self):
        """India (UTC+5:30, no DST)."""
        result = get_utc_offsets_for_month("Asia/Kolkata", 6)
        assert len(result) == 1
        assert result[0]["abbr"] == "IST"
        assert result[0]["utc_offset_hours"] == 5.5

    def test_southern_hemisphere_dst(self):
        """Australia/Sydney in October - AEST to AEDT transition."""
        result = get_utc_offsets_for_month("Australia/Sydney", 10)
        assert len(result) == 2
        # Sorted descending: AEDT (+11) before AEST (+10)
        assert result[0]["utc_offset_hours"] == 11.0
        assert result[1]["utc_offset_hours"] == 10.0

    def test_none_timezone(self):
        assert get_utc_offsets_for_month(None, 6) == []

    def test_empty_string_timezone(self):
        assert get_utc_offsets_for_month("", 6) == []

    def test_invalid_timezone(self):
        assert get_utc_offsets_for_month("Not/A/Timezone", 6) == []

    def test_all_months_return_valid_results(self):
        """Every month should return 1 or 2 offsets for a valid timezone."""
        for month in range(1, 13):
            result = get_utc_offsets_for_month("America/Chicago", month)
            assert 1 <= len(result) <= 2, f"Month {month} returned {len(result)} offsets"

    def test_sort_order_descending(self):
        """Offsets sorted descending by utc_offset_hours."""
        result = get_utc_offsets_for_month("America/Los_Angeles", 3)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]["utc_offset_hours"] >= result[i + 1]["utc_offset_hours"]
