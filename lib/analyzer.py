import datetime
import io
import os

import appdirs
import pandas as pd
import pytz
import requests
from dateutil.relativedelta import relativedelta
from enum import IntEnum

from lib.utils import say


class FlightCondition(IntEnum):
    LIFR = 1
    IFR = 2
    MVFR = 3
    VFR = 4


class MetarArchive:
    CACHE_DIR = appdirs.user_cache_dir("metar_calendar")
    NUM_MONTHS = 37

    def __init__(self, airport_code):
        self.code = airport_code.upper().strip()

    def _cache_filename(self):
        fn = os.path.join(self.CACHE_DIR, self.code + ".parquet")
        dirn = os.path.dirname(fn)
        if not os.path.exists(dirn):
            os.makedirs(dirn)
        return fn

    def _fetch(self):
        end_date = datetime.datetime.now(datetime.UTC)
        start_date = end_date - relativedelta(months=self.NUM_MONTHS)
        say(f'Fetching data for {self.code}')

        url = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
        params = {
            'station': self.code,
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

        df = pd.read_csv(io.StringIO(resp.content.decode('utf8', errors='ignore')))

        # Rename and parse date column
        df = df.rename({'valid': 'date'}, axis=1)
        df = df.sort_values('date').reset_index(drop=True)
        df['date'] = df['date'].apply(lambda d: datetime.datetime.strptime(
            d, "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC))

        # Keep only columns we need for flight rule classification
        needed_cols = ['date', 'vsby', 'skyc1', 'skyc2', 'skyc3', 'skyc4',
                      'skyl1', 'skyl2', 'skyl3', 'skyl4']
        existing_cols = [col for col in needed_cols if col in df.columns]
        df = df[existing_cols]

        # Convert visibility and sky levels to numeric (coerce errors to NaN)
        for col in ['vsby', 'skyl1', 'skyl2', 'skyl3', 'skyl4']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert sky condition codes to strings to avoid any mixed type issues
        for col in ['skyc1', 'skyc2', 'skyc3', 'skyc4']:
            if col in df.columns:
                df[col] = df[col].astype(str)

        say(f'Fetched {len(df)} rows from {df["date"].min()} to {df["date"].max()}')
        return df

    def get_dataframe(self, force=False):
        if force or not os.path.exists(self._cache_filename()):
            df = self._fetch()
            df.to_parquet(self._cache_filename())

        return pd.read_parquet(self._cache_filename())


class METARAnalyzer:
    def __init__(self, airport_code: str):
        self.airport_code = airport_code.upper().strip()
        self._archive = MetarArchive(airport_code)

    def _annotate_with_flightrule(self, df):
        def classify(obs):
            # Get lowest ceiling (broken or overcast layer)
            ceil = 100000

            for i in range(4):
                condition = obs.get(f'skyc{i+1}', None)
                height = obs.get(f'skyl{i+1}', None)
                if pd.isna(condition) or pd.isna(height):
                    continue
                if condition not in ('BKN', 'OVC', 'VV'):
                    continue
                if not ceil or height < ceil:
                    ceil = height

            # Get visibility
            vis = obs['vsby']

            if ceil >= 3000 and vis >= 5:
                return FlightCondition.VFR
            if ceil >= 1000 and vis >= 3:
                return FlightCondition.MVFR
            if ceil >= 500 and vis >= 1:
                return FlightCondition.IFR
            return FlightCondition.LIFR

        # Classify each observation according to flight rule
        df['Sky Condition'] = df.apply(classify, axis=1)

    def _get_hourly_for_month(self, df, month):
        # Find just observations from the requested month
        df = df.loc[df['date'].dt.month == month].copy()

        # Annotate each observation with its flight rule
        self._annotate_with_flightrule(df)

        # Move all timestamps forward by 10 minutes, so that an observation at 17:53
        # counts as the weather for 18:00.
        #
        # In cases where we have more than one observation in a single
        # hour, find the worst flight rule that occurred during that hour
        grouping = (df['date'] + datetime.timedelta(minutes=0)).dt.floor('1h')
        worst_every_hour = df.groupby(grouping)['Sky Condition'].agg('min')

        # For every one of the 24 hours, count how many times a flight
        # condition occurred during that hour
        hourly = (worst_every_hour.groupby(worst_every_hour.index.hour)
                  .value_counts().unstack().fillna(0))

        # Convert raw counts into percentages
        hourly = hourly.apply(lambda row: row / row.sum(), axis=1)

        # Rename the axes
        hourly.index = hourly.index.rename('UTC hour')
        hourly = hourly.rename({r.value: r.name for r in FlightCondition}, axis=1)

        # Ensure all flight condition columns exist (add missing ones with zeros)
        for condition in ['VFR', 'MVFR', 'IFR', 'LIFR']:
            if condition not in hourly.columns:
                hourly[condition] = 0.0

        # Reverse column order so VFR is on bottom (plotly stacks left to right)
        hourly = hourly[['VFR', 'MVFR', 'IFR', 'LIFR']]

        return hourly

    def get_hourly_statistics(self, month: int, force_refresh: bool = False) -> pd.DataFrame:
        df = self._archive.get_dataframe(force=force_refresh)
        hourly = self._get_hourly_for_month(df, month)

        hourly.attrs['airport'] = self.airport_code
        hourly.attrs['month'] = month

        return hourly
