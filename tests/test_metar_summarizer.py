import tempfile
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from lib.cache import Cache
from lib.metar_summarizer import MetarSummarizer
from lib.storage import LocalFileStorage
from .test_utils import mock_requests_get


class TestMetarSummarizer:
    """Tests for MetarSummarizer class."""

    @pytest.fixture
    def cache(self):
        """Create a cache with local file storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(tmpdir)
            yield Cache(storage)

    def test_initialization(self, cache):
        """Test that MetarSummarizer initializes with a cache and retriever."""
        summarizer = MetarSummarizer(cache)
        assert summarizer.cache == cache
        assert summarizer.retriever is not None

    @patch('lib.raw_metar_retriever.requests.get')
    def test_get_returns_good_dataframe(self, mock_requests, cache):
        """Test that get() returns a DataFrame with correct columns and index."""
        mock_requests.side_effect = mock_requests_get

        summarizer = MetarSummarizer(cache)
        df = summarizer.get("KPAO")

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ['vsby', 'ceiling']
        assert pd.api.types.is_datetime64_any_dtype(df.index)
        assert df.attrs['airport'] == 'KPAO'

    @patch('lib.raw_metar_retriever.requests.get')
    def test_hourly_aggregation(self, mock_requests, cache):
        """Test that observations are aggregated by hour."""
        mock_requests.side_effect = mock_requests_get

        summarizer = MetarSummarizer(cache)
        df = summarizer.get("KPAO")

        # Real data should have many hours of observations
        assert len(df) > 100

        # Each timestamp should be floored to the hour (0 minutes, 0 seconds, 0 microseconds)
        for timestamp in df.index:
            assert timestamp.minute == 0
            assert timestamp.second == 0
            assert timestamp.microsecond == 0

        # All timestamps should be unique
        assert df.index.is_unique

    @patch('lib.raw_metar_retriever.requests.get')
    def test_visibility_and_ceiling_values(self, mock_requests, cache):
        """Test that visibility and ceiling values are reasonable."""
        mock_requests.side_effect = mock_requests_get

        summarizer = MetarSummarizer(cache)
        df = summarizer.get("KPAO")

        # Visibility should be between 0 and some reasonable max
        assert df['vsby'].min() >= 0
        assert df['vsby'].max() <= 50

        # Ceiling should be between 0 and 100000 (our "no ceiling" value)
        assert df['ceiling'].min() >= 0
        assert df['ceiling'].max() <= 100000

    @patch('lib.raw_metar_retriever.requests.get')
    def test_multiple_airports_cached_independently(self, mock_requests, cache):
        """Test that multiple airports are cached with separate parquet files."""
        mock_requests.side_effect = mock_requests_get

        summarizer = MetarSummarizer(cache)

        df1 = summarizer.get("KPAO")
        df2 = summarizer.get("KMSN")

        # Both should be dataframes
        assert isinstance(df1, pd.DataFrame)
        assert isinstance(df2, pd.DataFrame)

        # Should have been called twice
        assert mock_requests.call_count == 2

        # Verify separate cache files exist
        assert cache.storage.get("KPAO.summarized.parquet") is not None
        assert cache.storage.get("KMSN.summarized.parquet") is not None

        # Fetch again - should hit cache
        df1_cached = summarizer.get("KPAO")
        df2_cached = summarizer.get("KMSN")

        # Should still be only 2 calls (cached)
        assert mock_requests.call_count == 2

        # DataFrames should be equal
        pd.testing.assert_frame_equal(df1, df1_cached)
        pd.testing.assert_frame_equal(df2, df2_cached)

    @patch('lib.raw_metar_retriever.requests.get')
    def test_get_normalizes_airport_code(self, mock_requests, cache):
        """Test that airport codes are normalized."""
        mock_requests.side_effect = mock_requests_get

        summarizer = MetarSummarizer(cache)

        # Fetch with lowercase and spaces
        df1 = summarizer.get("  kpao  ")

        # Verify cache key was normalized
        assert cache.storage.get("KPAO.summarized.parquet") is not None

        # Fetch with normalized code should hit same cache
        df2 = summarizer.get("KPAO")

        # Should only have called requests.get once
        assert mock_requests.call_count == 1

        # DataFrames should be equal
        pd.testing.assert_frame_equal(df1, df2)

    @pytest.mark.parametrize("sky_layers,expected_ceiling", [
        # Scattered layers ignored, broken layer becomes ceiling
        (['SCT', 1000, 'SCT', 1500, 'BKN', 2000, 'OVC', 3000], 2000),
        # Scattered-only has no ceiling
        (['SCT', 2000], 100000),
        # Single broken layer
        (['BKN', 4000], 4000),
        # Scattered ignored, overcast becomes ceiling
        (['SCT', 2000, 'OVC', 5000], 5000),
        # Vertical visibility is a ceiling
        (['VV', 200], 200),
        # High scattered-only has no ceiling
        (['SCT', 15000], 100000),
        # Lowest BKN/OVC layer wins
        (['BKN', 8000, 'BKN', 3000, 'OVC', 10000], 3000),
        # Clear skies (CLR) has no ceiling
        (['CLR'], 100000),
        # Few clouds (FEW) don't create ceiling
        (['FEW', 1000], 100000),
        # Empty observation
        ([], 100000),
        # All four layers populated - lowest ceiling layer wins
        (['FEW', 500, 'SCT', 1000, 'BKN', 1500, 'OVC', 2000], 1500),
        # Multiple OVC layers - lowest wins
        (['OVC', 3000, 'OVC', 1500], 1500),
        # Single OVC layer
        (['OVC', 2000], 2000),
    ])
    def test_calculate_ceiling(self, cache, sky_layers, expected_ceiling):
        """Test ceiling calculation with various sky conditions."""
        summarizer = MetarSummarizer(cache)

        obs = pd.Series({})
        # Convert flat array to skyc1/skyl1, skyc2/skyl2, etc.
        for i in range(0, len(sky_layers), 2):
            layer_num = i // 2 + 1
            obs[f'skyc{layer_num}'] = sky_layers[i]
            if i + 1 < len(sky_layers):
                obs[f'skyl{layer_num}'] = sky_layers[i + 1]

        assert summarizer._calculate_ceiling(obs) == expected_ceiling

    @patch('lib.raw_metar_retriever.requests.get')
    def test_hourly_aggregation_takes_minimum(self, mock_requests, cache):
        """Test that hourly aggregation takes minimum visibility and ceiling within each hour."""
        # Create synthetic CSV with multiple observations across several hours
        # Each hour has multiple observations with varying visibility and ceiling
        synthetic_csv = b"""station,valid,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4
KTEST,2025-01-01 10:05,10.0,SCT,2000,BKN,3000,,,
KTEST,2025-01-01 10:20,5.0,BKN,1500,OVC,2500,,,
KTEST,2025-01-01 10:35,8.0,OVC,2000,,,,
KTEST,2025-01-01 10:50,7.0,BKN,2500,,,,
KTEST,2025-01-01 11:10,3.0,BKN,4000,,,,
KTEST,2025-01-01 11:25,7.0,OVC,5000,,,,
KTEST,2025-01-01 11:40,4.0,SCT,3000,BKN,3500,,
KTEST,2025-01-01 11:55,9.0,OVC,4500,,,,
KTEST,2025-01-01 12:00,2.0,VV,300,,,,
KTEST,2025-01-01 12:15,6.0,BKN,1000,OVC,2000,,
KTEST,2025-01-01 12:30,10.0,FEW,500,SCT,1500,BKN,5000,
KTEST,2025-01-01 12:45,8.0,SCT,2000,OVC,6000,,
KTEST,2025-01-01 13:05,1.0,VV,200,,,,
KTEST,2025-01-01 13:20,4.0,BKN,800,,,,
KTEST,2025-01-01 13:40,5.0,OVC,1200,,,,
"""

        # Mock requests to return synthetic data
        mock_response = Mock()
        mock_response.content = synthetic_csv
        mock_response.raise_for_status = Mock()
        mock_requests.return_value = mock_response

        summarizer = MetarSummarizer(cache)
        df = summarizer.get("KTEST")

        # Should have exactly 4 hours
        assert len(df) == 4

        # Hour 1 (10:00): visibility min(10.0, 5.0, 8.0, 7.0) = 5.0
        #                 ceiling min(3000, 1500, 2000, 2500) = 1500
        hour1 = df.loc[df.index[0]]
        assert hour1['vsby'] == 5.0
        assert hour1['ceiling'] == 1500

        # Hour 2 (11:00): visibility min(3.0, 7.0, 4.0, 9.0) = 3.0
        #                 ceiling min(4000, 5000, 3500, 4500) = 3500
        hour2 = df.loc[df.index[1]]
        assert hour2['vsby'] == 3.0
        assert hour2['ceiling'] == 3500

        # Hour 3 (12:00): visibility min(2.0, 6.0, 10.0, 8.0) = 2.0
        #                 ceiling min(300, 1000, 5000, 6000) = 300
        hour3 = df.loc[df.index[2]]
        assert hour3['vsby'] == 2.0
        assert hour3['ceiling'] == 300

        # Hour 4 (13:00): visibility min(1.0, 4.0, 5.0) = 1.0
        #                 ceiling min(200, 800, 1200) = 200
        hour4 = df.loc[df.index[3]]
        assert hour4['vsby'] == 1.0
        assert hour4['ceiling'] == 200
