"""Common test utilities for loading real METAR test data."""
import gzip
import os
from unittest.mock import Mock


def load_test_data(airport: str) -> bytes:
    """Load real METAR test data from tests/data directory."""
    # Use absolute path to work even when cwd changes
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_data_path = os.path.join(test_dir, 'data', f'{airport}.csv.gz')
    with gzip.open(test_data_path, 'rb') as f:
        return f.read()


def mock_requests_get(*args, **kwargs):
    """Mock requests.get to return real test data."""
    station = kwargs['params']['station']
    mock_response = Mock()
    mock_response.content = load_test_data(station)
    mock_response.raise_for_status = Mock()
    return mock_response
