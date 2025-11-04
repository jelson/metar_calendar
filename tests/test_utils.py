"""Common test utilities for loading real METAR test data."""
import glob
import gzip
import os
from unittest.mock import Mock

# Constants used across tests
PNG_MAGIC_BYTES = b'\x89PNG\r\n\x1a\n'
FLIGHT_CONDITIONS = ['VFR', 'MVFR', 'IFR', 'LIFR']


def get_test_airports() -> list[str]:
    """Get list of all airports for which we have test data."""
    test_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    # Find all .csv.gz files and extract airport codes
    data_files = glob.glob(os.path.join(test_data_dir, '*.csv.gz'))
    airports = [os.path.basename(f).replace('.csv.gz', '') for f in data_files]
    return sorted(airports)


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


def assert_valid_png(file_path: str) -> None:
    """Assert that a file is a valid PNG by checking magic bytes."""
    with open(file_path, 'rb') as f:
        assert f.read(8) == PNG_MAGIC_BYTES, f"{file_path} is not a valid PNG"
