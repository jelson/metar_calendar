import os
import sys
import traceback
from pathlib import Path

import appdirs
import cherrypy
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from lib.analyzer import METARAnalyzer  # noqa: E402
from lib.storage import LocalFileStorage  # noqa: E402
from lib.sun_utils import get_daylight_utc_hours  # noqa: E402
from lib.timezone_utils import get_utc_offsets_for_month  # noqa: E402
from lib.utils import say  # noqa: E402

METADATA_PATH = Path(__file__).parent / 'data' / 'airport_metadata.parquet'

# Host configuration
PRODUCTION_FRONTEND = 'https://www.avmapper.com'
DEV_FRONTEND = 'http://localhost:4000'


class MetarAPI:
    def __init__(self, dev_mode=False):
        self.dev_mode = dev_mode
        self.frontend_origin = DEV_FRONTEND if dev_mode else PRODUCTION_FRONTEND

        # Create storage with local file storage
        cache_dir = appdirs.user_cache_dir("metar_calendar")
        self.storage = LocalFileStorage(cache_dir)

        # Load airport metadata (timezone info, etc.)
        if not METADATA_PATH.exists():
            raise FileNotFoundError(f"Airport metadata not found at {METADATA_PATH}")
        self.airport_metadata = pd.read_parquet(METADATA_PATH)
        say(f"Loaded airport metadata for {len(self.airport_metadata)} airports")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def statistics(self, airport_code, month):
        """GET /api/statistics?airport_code=KSMO&month=6"""
        try:
            month = int(month)
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")

            analyzer = METARAnalyzer(airport_code, self.storage)
            hourly = analyzer.get_hourly_statistics(month)

            # Look up airport metadata for timezone and daylight computation
            tz_name = None
            daylight_utc = None
            if airport_code in self.airport_metadata.index:
                meta = self.airport_metadata.loc[airport_code]
                tz_name = meta.get('tz')
                if pd.isna(tz_name):
                    tz_name = None
                lat = meta.get('lat')
                lon = meta.get('lon')
                if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                    daylight_utc = get_daylight_utc_hours(float(lat), float(lon), month)
            utc_offsets = get_utc_offsets_for_month(tz_name, month)

            # Convert DataFrame to JSON-serializable dict
            return {
                'airport': hourly.attrs.get('airport'),
                'month': hourly.attrs.get('month'),
                'utc_offsets': utc_offsets,
                'daylight_utc': daylight_utc,
                'hourly_stats': {
                    int(hour): {
                        'VFR': float(row['VFR']),
                        'MVFR': float(row['MVFR']),
                        'IFR': float(row['IFR']),
                        'LIFR': float(row['LIFR']),
                    }
                    for hour, row in hourly.iterrows()
                }
            }
        except Exception as e:
            say(f'API error for {airport_code}: {type(e).__name__}: {str(e)}')
            traceback.print_exc()
            cherrypy.response.status = 400
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """GET /api/health"""
        return {'status': 'ok'}


def create_app(dev_mode=False):
    """Create and configure the CherryPy application"""
    api = MetarAPI(dev_mode=dev_mode)

    conf = {
        '/': {
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [
                ('Access-Control-Allow-Origin', api.frontend_origin),
                ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type'),
            ],
        }
    }

    return api, conf


if __name__ == '__main__':
    # Running directly - use development mode
    api, conf = create_app(dev_mode=True)

    cherrypy.tree.mount(api, '/api', conf)
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 5000,
    })

    say("Starting METAR API server in DEVELOPMENT mode")

    cherrypy.engine.start()
    cherrypy.engine.block()
else:
    # Loaded by uwsgi - production server
    api, conf = create_app(dev_mode=False)
    cherrypy.tree.mount(api, '/', conf)
    cherrypy.config.update({
        'log.screen': True,
        'environment': 'production',
        'tools.proxy.on': True,
    })

    # "application" is the magic function called by uwsgi on each request
    def application(environ, start_response):
        return cherrypy.tree(environ, start_response)
