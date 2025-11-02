import os
import sys
import traceback

import cherrypy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from lib.analyzer import METARAnalyzer  # noqa: E402
from lib.visualizer import METARVisualizer  # noqa: E402
from lib.utils import say  # noqa: E402

# Host configuration
PRODUCTION_FRONTEND = 'https://www.avmapper.com'
DEV_FRONTEND = 'http://localhost:4000'


class MetarAPI:
    def __init__(self, dev_mode=False):
        self.dev_mode = dev_mode
        self.frontend_origin = DEV_FRONTEND if dev_mode else PRODUCTION_FRONTEND

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def statistics(self, airport_code, month):
        """GET /api/statistics?airport_code=KSMO&month=6"""
        try:
            month = int(month)
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")

            analyzer = METARAnalyzer(airport_code)
            hourly = analyzer.get_hourly_statistics(month)

            return METARVisualizer.to_dict(hourly)
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


# "application" is the magic function called by uwsgi
def application(environ, start_response):
    api, conf = create_app(dev_mode=False)
    cherrypy.tree.mount(api, '/', conf)
    cherrypy.config.update({
        'log.screen': True,
        'environment': 'production',
        'tools.proxy.on': True,
    })
    return cherrypy.tree(environ, start_response)


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
