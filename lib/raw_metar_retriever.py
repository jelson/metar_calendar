import datetime

import requests
from dateutil.relativedelta import relativedelta

from lib.cache import Cache
from lib.utils import say


class RawMetarRetriever:
    """Retrieves raw METAR CSV data from IEM, with caching support."""

    NUM_MONTHS = 37

    def __init__(self, cache: Cache):
        """Initialize retriever with a cache backend.

        Args:
            cache: Cache instance for storing/retrieving raw CSV data
        """
        self.cache = cache

    def get(self, airport: str) -> bytes:
        """Get raw METAR CSV data for an airport.

        Args:
            airport: Airport code (e.g., 'KSFO', 'KPAO')

        Returns:
            Raw CSV data as bytes
        """
        airport = airport.upper().strip()
        cache_key = f"{airport}.raw.csv"

        def fetch_from_iem() -> bytes:
            """Fetch fresh data from IEM."""
            end_date = datetime.datetime.now(datetime.UTC)
            start_date = end_date - relativedelta(months=self.NUM_MONTHS)
            say(f'Fetching data for {airport}')

            url = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
            params = {
                'station': airport,
                'data': 'all',
                'year1': start_date.year,
                'month1': start_date.month,
                'day1': 1,
                'year2': end_date.year,
                'month2': end_date.month,
                'day2': end_date.day,
                'tz': 'Etc/UTC',
                'format': 'onlycomma',
                'latlon': 'no',
                'elev': 'no',
                'missing': 'empty',
                'trace': 'T',
                'direct': 'no',
                'report_type': [3, 4],
            }

            resp = requests.get(url, params=params)
            resp.raise_for_status()
            return resp.content

        return self.cache.get(cache_key, fetch_from_iem)
