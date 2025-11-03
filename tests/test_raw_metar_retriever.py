import datetime
import tempfile
from unittest.mock import Mock, patch

import pytest
from dateutil.relativedelta import relativedelta

from lib.cache import Cache
from lib.raw_metar_retriever import RawMetarRetriever
from lib.storage import LocalFileStorage


def make_test_csv(airport: str) -> bytes:
    """Generate test CSV data for a given airport."""
    return f"station,valid,vsby\n{airport},2025-11-01 12:00,10.0\n".encode()


def mock_get(*args, **kwargs):
    """Mock requests.get to return airport-specific test data."""
    station = kwargs['params']['station']
    mock_response = Mock()
    mock_response.content = make_test_csv(station)
    mock_response.raise_for_status = Mock()
    return mock_response


class TestRawMetarRetriever:
    """Tests for RawMetarRetriever class."""

    @pytest.fixture
    def cache(self):
        """Create a cache with local file storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(tmpdir)
            yield Cache(storage)

    def test_initialization(self, cache):
        """Test that RawMetarRetriever initializes with a cache."""
        retriever = RawMetarRetriever(cache)
        assert retriever.cache == cache
        assert retriever.NUM_MONTHS == 37

    def test_get_normalizes_airport_code(self, cache):
        """Test that airport codes are normalized and cache key format is {AIRPORT}.raw.csv."""
        # Pre-populate cache with data for KPAO
        cache.storage.put("KPAO.raw.csv", make_test_csv("KPAO"))

        retriever = RawMetarRetriever(cache)

        # Test lowercase with spaces
        result = retriever.get("  kpao  ")

        # Verify result
        assert result == make_test_csv("KPAO")

    @patch('lib.raw_metar_retriever.requests.get')
    def test_fetch_called_on_cache_miss(self, mock_requests, cache):
        """Test that IEM is fetched when cache misses."""
        mock_requests.side_effect = mock_get

        retriever = RawMetarRetriever(cache)
        result = retriever.get("KPAO")

        # Verify result
        assert result == make_test_csv("KPAO")

        # Verify requests.get was called
        assert mock_requests.called
        call_args = mock_requests.call_args
        assert call_args[1]['params']['station'] == 'KPAO'

        # Verify data was cached
        cached_data = cache.storage.get("KPAO.raw.csv")
        assert cached_data == make_test_csv("KPAO")

    @patch('lib.raw_metar_retriever.requests.get')
    def test_fetch_constructs_correct_url_params(self, mock_requests, cache):
        """Test that IEM API is called with correct parameters."""
        # Calculate expected date range
        now = datetime.datetime.now(datetime.UTC)
        expected_start = now - relativedelta(months=37)

        mock_requests.side_effect = mock_get

        retriever = RawMetarRetriever(cache)
        retriever.get("KSFO")

        # Verify requests.get was called with correct parameters
        assert mock_requests.called
        call_args = mock_requests.call_args

        assert call_args[0][0] == 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'

        params = call_args[1]['params']
        assert params['station'] == 'KSFO'
        assert params['data'] == 'all'
        assert params['year1'] == expected_start.year
        assert params['month1'] == expected_start.month
        assert params['day1'] == 1
        assert params['year2'] == now.year
        assert params['month2'] == now.month
        assert params['day2'] == now.day
        assert params['tz'] == 'Etc/UTC'
        assert params['format'] == 'onlycomma'
        assert params['latlon'] == 'no'
        assert params['elev'] == 'no'
        assert params['missing'] == 'empty'
        assert params['trace'] == 'T'
        assert params['direct'] == 'no'
        assert params['report_type'] == [3, 4]

    @patch('lib.raw_metar_retriever.requests.get')
    def test_cache_hit_returns_cached_data(self, mock_requests, cache):
        """Test that cached data is returned without fetching from IEM."""
        cached_data = make_test_csv("KSMO")

        # Pre-populate cache
        cache.storage.put("KSMO.raw.csv", cached_data)

        retriever = RawMetarRetriever(cache)
        result = retriever.get("KSMO")

        assert result == cached_data

        # Verify requests.get was NOT called
        assert not mock_requests.called

    @patch('lib.raw_metar_retriever.requests.get')
    def test_multiple_airports_cached(self, mock_requests, cache):
        """Test that multiple airports are cached independently."""
        mock_requests.side_effect = mock_get

        retriever = RawMetarRetriever(cache)

        # First fetch - should hit IEM for all three
        assert retriever.get("KPAO") == make_test_csv("KPAO")
        assert retriever.get("KSFO") == make_test_csv("KSFO")
        assert retriever.get("KMSN") == make_test_csv("KMSN")

        # Verify requests.get was called exactly 3 times
        assert mock_requests.call_count == 3

        # Second fetch - should hit cache, not IEM
        assert retriever.get("KPAO") == make_test_csv("KPAO")
        assert retriever.get("KSFO") == make_test_csv("KSFO")
        assert retriever.get("KMSN") == make_test_csv("KMSN")

        # Verify requests.get was still only called 3 times (no new calls)
        assert mock_requests.call_count == 3

    @patch('lib.raw_metar_retriever.requests.get')
    def test_http_error_propagates(self, mock_requests, cache):
        """Test that HTTP errors from IEM are propagated."""
        # Setup mock response with HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 404")
        mock_requests.return_value = mock_response

        retriever = RawMetarRetriever(cache)

        with pytest.raises(Exception, match="HTTP 404"):
            retriever.get("INVALID")
