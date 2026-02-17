"""Tests for the airport data conversion script."""
import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# Import the module to verify all dependencies are available
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'website', 'frontend', '_data'))
import convert_airports  # noqa: E402


# Minimal OurAirports CSV data for testing
OURAIRPORTS_CSV = """\
id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,gps_code,local_code,home_link,wikipedia_link,keywords
4185,LFPG,large_airport,Charles de Gaulle International Airport,49.012798,2.55,392,EU,FR,FR-IDF,"Paris (Roissy-en-France, Val-d'Oise)",yes,LFPG,CDG,LFPG,,,,"PAR"
2513,KSMO,medium_airport,Santa Monica Municipal Airport,34.0158,-118.4513,177,NA,US,US-CA,Santa Monica,no,KSMO,SMO,KSMO,SMO,,,
9999,XNOP,small_airport,No Match Airport,0.0,0.0,0,NA,US,US-XX,Nowhere,no,XNOP,,XNOP,XNOP,,,
"""

# Minimal IEM stations CSV data for testing
IEM_STATIONS_CSV = """\
stid,station_name,lat,lon
LFPG,PARIS/CDG,49.0128,2.55
SMO,SANTA MONICA,34.0158,-118.4513
"""


@pytest.fixture
def mock_http():
    """Mock HTTP responses for both IEM and OurAirports."""
    with patch.object(convert_airports, 'session') as mock_session:
        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if 'mesonet' in url:
                resp.text = IEM_STATIONS_CSV
            elif 'ourairports' in url:
                resp.text = OURAIRPORTS_CSV
            return resp
        mock_session.get.side_effect = fake_get
        yield mock_session


class TestConvertAirports:
    def test_imports(self):
        """Verify all dependencies are importable."""
        import airportsdata  # noqa: F401
        import requests_cache  # noqa: F401

    def test_conversion_output_schema(self, mock_http):
        """Test that convert_airports produces valid JSON with expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, 'airports.json')
            parquet_path = os.path.join(tmpdir, 'metadata.parquet')

            with patch.object(convert_airports, 'OUTPUT_JSON', type(convert_airports.OUTPUT_JSON)(json_path)), \
                 patch.object(convert_airports, 'OUTPUT_METADATA', type(convert_airports.OUTPUT_METADATA)(parquet_path)):
                convert_airports.convert_airports()

            # Verify JSON was created
            assert os.path.exists(json_path)
            with open(json_path) as f:
                airports = json.load(f)

            assert len(airports) > 0

            # Verify schema of each airport record
            required_fields = {'display', 'codes', 'name', 'location', 'size', 'query'}
            for airport in airports:
                assert required_fields.issubset(airport.keys()), \
                    f"Airport {airport.get('display')} missing fields: {required_fields - airport.keys()}"
                assert isinstance(airport['codes'], list)
                assert isinstance(airport['size'], int)
                assert airport['size'] in (0, 1, 2, 3)

    def test_size_field_values(self, mock_http):
        """Test that airport type maps to correct size values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, 'airports.json')
            parquet_path = os.path.join(tmpdir, 'metadata.parquet')

            with patch.object(convert_airports, 'OUTPUT_JSON', type(convert_airports.OUTPUT_JSON)(json_path)), \
                 patch.object(convert_airports, 'OUTPUT_METADATA', type(convert_airports.OUTPUT_METADATA)(parquet_path)):
                convert_airports.convert_airports()

            with open(json_path) as f:
                airports = json.load(f)

            by_display = {a['display']: a for a in airports}

            # CDG is a large_airport -> size 0
            if 'LFPG' in by_display:
                assert by_display['LFPG']['size'] == 0

            # SMO is a medium_airport -> size 1
            if 'KSMO' in by_display:
                assert by_display['KSMO']['size'] == 1

    def test_no_match_airports_excluded(self, mock_http):
        """Test that airports without IEM station matches are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, 'airports.json')
            parquet_path = os.path.join(tmpdir, 'metadata.parquet')

            with patch.object(convert_airports, 'OUTPUT_JSON', type(convert_airports.OUTPUT_JSON)(json_path)), \
                 patch.object(convert_airports, 'OUTPUT_METADATA', type(convert_airports.OUTPUT_METADATA)(parquet_path)):
                convert_airports.convert_airports()

            with open(json_path) as f:
                airports = json.load(f)

            displays = {a['display'] for a in airports}
            # XNOP has no matching IEM station (coords 0,0 don't match anything)
            assert 'XNOP' not in displays
