import pandas as pd
import pytest
import tempfile
from unittest.mock import patch

from lib.analyzer import METARAnalyzer, FlightCondition
from lib.storage import LocalFileStorage
from .test_utils import mock_requests_get


class TestFlightCondition:
    def test_enum_values(self):
        # FlightCondition is an IntEnum with these values
        assert FlightCondition.LIFR == 1
        assert FlightCondition.IFR == 2
        assert FlightCondition.MVFR == 3
        assert FlightCondition.VFR == 4

    def test_enum_names(self):
        assert FlightCondition.LIFR.name == 'LIFR'
        assert FlightCondition.IFR.name == 'IFR'
        assert FlightCondition.MVFR.name == 'MVFR'
        assert FlightCondition.VFR.name == 'VFR'


class TestMETARAnalyzer:
    @pytest.fixture
    def storage(self):
        """Create storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalFileStorage(tmpdir)

    @patch('lib.raw_metar_retriever.requests.get')
    def test_initialization(self, mock_requests, storage):
        """Test that METARAnalyzer initializes and fetches summary data."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        assert analyzer.airport_code == 'KPAO'
        assert analyzer.summarizer is not None
        assert isinstance(analyzer.hourly_summary, pd.DataFrame)
        assert len(analyzer.hourly_summary) > 0

    @pytest.mark.parametrize("airport", ['KPAO', 'KCOE', 'KMSN', 'KRNT'])
    @patch('lib.raw_metar_retriever.requests.get')
    def test_hourly_stats_structure(self, mock_requests, storage, airport):
        """Test that get_hourly_statistics returns proper DataFrame structure."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)

        # Test all 12 months
        for month in range(1, 13):
            result = analyzer.get_hourly_statistics(month)

            # Should return a DataFrame with hours as index
            assert isinstance(result, pd.DataFrame)
            assert len(result) <= 24  # At most 24 hours

            # All four columns should exist even if some are 0
            assert all(col in result.columns for col in ['VFR', 'MVFR', 'IFR', 'LIFR'])

            # Check attributes are set
            assert result.attrs.get('airport') == airport
            assert result.attrs.get('month') == month

    @patch('lib.raw_metar_retriever.requests.get')
    def test_classification_logic(self, mock_requests, storage):
        """Test that flight conditions are properly classified."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        # VFR: ceiling >= 3000 AND visibility >= 5
        assert analyzer._classify_flight_condition(5000, 10) == FlightCondition.VFR
        assert analyzer._classify_flight_condition(3000, 5) == FlightCondition.VFR  # Boundary

        # VFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(2999, 10) == FlightCondition.MVFR  # Ceiling just under VFR

        # VFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 4.9) == FlightCondition.MVFR  # Visibility just under VFR

        # MVFR: ceiling >= 1000 AND visibility >= 3
        assert analyzer._classify_flight_condition(2000, 4) == FlightCondition.MVFR
        assert analyzer._classify_flight_condition(1000, 3) == FlightCondition.MVFR  # Boundary

        # MVFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(999, 10) == FlightCondition.IFR  # Ceiling just under MVFR

        # MVFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 2.9) == FlightCondition.IFR  # Visibility just under MVFR

        # IFR: ceiling >= 500 AND visibility >= 1
        assert analyzer._classify_flight_condition(800, 2) == FlightCondition.IFR
        assert analyzer._classify_flight_condition(500, 1) == FlightCondition.IFR  # Boundary

        # IFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(499, 10) == FlightCondition.LIFR  # Ceiling just under IFR

        # IFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 0.9) == FlightCondition.LIFR  # Visibility just under IFR

        # LIFR: ceiling < 500 OR visibility < 1
        assert analyzer._classify_flight_condition(300, 0.5) == FlightCondition.LIFR
        assert analyzer._classify_flight_condition(100, 0.25) == FlightCondition.LIFR  # Very low ceiling
        assert analyzer._classify_flight_condition(200, 10) == FlightCondition.LIFR  # Low ceiling, good visibility
        assert analyzer._classify_flight_condition(5000, 0.5) == FlightCondition.LIFR  # Good ceiling, low visibility

    @patch('lib.raw_metar_retriever.requests.get')
    def test_percentages_sum_to_one(self, mock_requests, storage):
        """Test that percentages for each hour sum to 1."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)
        result = analyzer.get_hourly_statistics(1)

        # Each row should sum to 1.0 (100%)
        for hour, row in result.iterrows():
            total = row['VFR'] + row['MVFR'] + row['IFR'] + row['LIFR']
            assert abs(total - 1.0) < 0.001, f"Hour {hour} sums to {total}, not 1.0"

    @patch('lib.raw_metar_retriever.requests.get')
    def test_multiple_months(self, mock_requests, storage):
        """Test that we can request statistics for different months from same analyzer."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        # Request multiple months
        jan = analyzer.get_hourly_statistics(1)
        jun = analyzer.get_hourly_statistics(6)

        # Both should be valid DataFrames
        assert isinstance(jan, pd.DataFrame)
        assert isinstance(jun, pd.DataFrame)

        # Attributes should reflect the correct month
        assert jan.attrs.get('month') == 1
        assert jun.attrs.get('month') == 6

        # Should not have made additional requests (using cached summary)
        assert mock_requests.call_count == 1
