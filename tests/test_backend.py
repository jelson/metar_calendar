import json
import os
import sys
import tempfile

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cherrypy  # noqa: E402
from cherrypy.test import helper  # noqa: E402

from website.backend.app import MetarAPI, create_app  # noqa: E402
from .test_utils import mock_requests_get  # noqa: E402


class TestMetarAPI(helper.CPWebCase):
    @staticmethod
    def setup_server():
        api, conf = create_app(dev_mode=True)
        cherrypy.tree.mount(api, '/api', conf)

    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    def test_statistics_endpoint_success(self, mock_cache_dir, mock_requests):
        """Test statistics endpoint with real data."""
        mock_requests.side_effect = mock_requests_get

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir

            # Make request
            self.getPage('/api/statistics?airport_code=KPAO&month=6')

            # Verify response
            self.assertStatus('200 OK')
            self.assertHeader('Content-Type', 'application/json')

            response_data = json.loads(self.body.decode('utf-8'))
            assert response_data['airport'] == 'KPAO'
            assert response_data['month'] == 6
            assert 'hourly_stats' in response_data

            # JSON keys are strings, not integers
            hourly_stats = response_data['hourly_stats']
            assert isinstance(hourly_stats, dict)
            assert len(hourly_stats) > 0

            # Check first hour has all required fields
            first_hour_key = list(hourly_stats.keys())[0]
            first_hour = hourly_stats[first_hour_key]
            assert 'VFR' in first_hour
            assert 'MVFR' in first_hour
            assert 'IFR' in first_hour
            assert 'LIFR' in first_hour

    def test_statistics_endpoint_invalid_month(self):
        """Test that invalid month returns error."""
        # Make request with invalid month
        self.getPage('/api/statistics?airport_code=KPAO&month=13')

        # Should return 400 error
        self.assertStatus('400 Bad Request')

        response_data = json.loads(self.body.decode('utf-8'))
        assert 'error' in response_data

    def test_statistics_endpoint_missing_params(self):
        """Test that missing parameters returns error."""
        # Make request without required parameters
        self.getPage('/api/statistics?month=6')

        # CherryPy should return 404 or error
        assert self.status != '200 OK'


    def test_health_endpoint(self):
        # Make request to health endpoint
        self.getPage('/api/health')

        # Verify response
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'application/json')

        response_data = json.loads(self.body.decode('utf-8'))
        assert response_data['status'] == 'ok'

    def test_cors_headers_dev_mode(self):
        # Verify CORS headers are set correctly in dev mode
        self.getPage('/api/health')

        self.assertStatus('200 OK')
        self.assertHeader('Access-Control-Allow-Origin', 'http://localhost:4000')


class TestCreateApp:
    def test_create_app_dev_mode(self):
        api, conf = create_app(dev_mode=True)

        assert isinstance(api, MetarAPI)
        assert api.dev_mode is True
        assert api.frontend_origin == 'http://localhost:4000'
        assert '/' in conf
        assert 'tools.response_headers.headers' in conf['/']

    def test_create_app_production_mode(self):
        api, conf = create_app(dev_mode=False)

        assert isinstance(api, MetarAPI)
        assert api.dev_mode is False
        assert api.frontend_origin == 'https://www.avmapper.com'

    def test_cors_configuration(self):
        api, conf = create_app(dev_mode=True)

        headers = dict(conf['/']['tools.response_headers.headers'])
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == 'http://localhost:4000'
        assert headers['Access-Control-Allow-Methods'] == 'GET, OPTIONS'
