import datetime
import io

import pandas as pd
import pytz

from lib.cache import Cache
from lib.raw_metar_retriever import RawMetarRetriever
from lib.utils import say


class MetarSummarizer:
    """Given the raw CSV file of all weather data retrieved from the University of Iowa
    archive, do some post processing on it: parse, drop unneeded columns, determine the
    lowest ceiling of each observation, and if there's more than one observation in an
    hour, find the lowest ceiling and visibility during that hour. Store this post-processed
    data as a parquet file for later fast retrieval.
    """

    def __init__(self, cache: Cache):
        self.cache = cache
        self.retriever = RawMetarRetriever(cache)

    def _calculate_ceiling(self, obs):
        """Calculate the lowest ceiling from an observation.

        Args:
            obs: DataFrame row with skyc1-4 and skyl1-4 columns

        Returns:
            Lowest ceiling in feet, or 100000 if no ceiling
        """
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

        return ceil

    def _compute_hourly_minimums(self, airport: str) -> pd.DataFrame:
        """Compute hourly minimums from raw METAR data (internal helper).

        Fetches raw METAR CSV data and processes it into hourly minimums with:
        - Hour of day (indexed by datetime floored to hour)
        - Minimum visibility for that hour
        - Minimum ceiling for that hour
        - Maximum sustained wind (sknt) and gust for that hour
        - Wind direction (drct) at the strongest sustained wind of the hour
        - Mean temperature (tmpf) and dewpoint (dwpf), in Fahrenheit
        - Maximum precipitation (p01i), in inches
        - Present-weather codes (wxcodes) for the hour, space-joined

        Args:
            airport: Airport code (normalized, e.g., 'KSFO', 'KPAO')

        Returns:
            DataFrame indexed by hour with columns: vsby, ceiling, sknt, gust,
            drct, tmpf, dwpf, p01i, wxcodes
        """
        # Get raw CSV data
        raw_csv = self.retriever.get(airport)

        # Parse CSV into dataframe - only read columns we need for performance
        cols_needed = ['valid', 'vsby', 'skyc1', 'skyl1', 'skyc2', 'skyl2',
                       'skyc3', 'skyl3', 'skyc4', 'skyl4',
                       'drct', 'sknt', 'gust', 'tmpf', 'dwpf', 'p01i', 'wxcodes']
        df = pd.read_csv(io.StringIO(raw_csv.decode('utf8', errors='ignore')),
                         usecols=cols_needed, low_memory=False)

        # Rename and parse date column
        df = df.rename({'valid': 'date'}, axis=1)
        df = df.sort_values('date').reset_index(drop=True)
        df['date'] = df['date'].apply(lambda d: datetime.datetime.strptime(
            d, "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC))

        # Convert visibility, sky levels, wind and temperature/precip to
        # numeric (coerce errors to NaN, e.g. p01i sometimes reports 'T' for
        # a trace amount of precipitation)
        for col in ['vsby', 'skyl1', 'skyl2', 'skyl3', 'skyl4',
                    'drct', 'sknt', 'gust', 'tmpf', 'dwpf', 'p01i']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert sky condition codes to strings to avoid any mixed type issues
        for col in ['skyc1', 'skyc2', 'skyc3', 'skyc4']:
            if col in df.columns:
                df[col] = df[col].astype(str)

        # Present-weather codes (e.g. "-RA", "+TSRA", "SN") as a plain string,
        # empty for observations that reported none
        df['wxcodes'] = df['wxcodes'].fillna('').astype(str)

        say(f'Fetched {len(df)} rows from {df["date"].min()} to {df["date"].max()}')

        # Calculate ceiling for each observation
        df['ceiling'] = df.apply(self._calculate_ceiling, axis=1)

        # Group by hour: minimum visibility and ceiling, maximum sustained
        # wind and gust (the strongest wind is what matters to a pilot),
        # mean temperature and dewpoint, and maximum precipitation (p01i is
        # already a rolling one-hour total, so max avoids double-counting
        # when an hour has more than one observation)
        grouping = df['date'].dt.floor('1h')
        hourly = df.groupby(grouping).agg({
            'vsby': 'min',
            'ceiling': 'min',
            'sknt': 'max',
            'gust': 'max',
            'tmpf': 'mean',
            'dwpf': 'mean',
            'p01i': 'max',
            'wxcodes': lambda codes: ' '.join(c for c in codes if c),
        })

        # Wind direction: take the direction observed at the strongest
        # sustained wind of the hour. NaN speeds are filled with -1 so
        # idxmax never picks them unless the whole hour lacks wind data,
        # in which case the direction is masked out below.
        max_wind_idx = df['sknt'].fillna(-1).groupby(grouping).idxmax()
        hourly['drct'] = df.loc[max_wind_idx, 'drct'].values
        hourly.loc[hourly['sknt'].isna(), 'drct'] = float('nan')

        # Annotate with airport code
        hourly.attrs['airport'] = airport

        return hourly

    def get(self, airport: str) -> pd.DataFrame:
        """Get hourly summarized METAR data for an airport.

        Uses cache to store/retrieve processed parquet files.

        Args:
            airport: Airport code

        Returns:
            DataFrame indexed by day and hour with columns: vsby, ceiling
        """
        airport = airport.upper().strip()
        # v4: adds wxcodes (v3 added tmpf, dwpf, p01i; v2 added sknt, gust, drct)
        cache_key = f"{airport}.summarized.v4.parquet"

        def compute_and_serialize() -> bytes:
            """Compute the summary and serialize to parquet bytes."""
            hourly = self._compute_hourly_minimums(airport)
            buffer = io.BytesIO()
            hourly.to_parquet(buffer)
            return buffer.getvalue()

        # Get from cache (or compute if not cached)
        parquet_bytes = self.cache.get(cache_key, compute_and_serialize)

        # Deserialize from parquet
        return pd.read_parquet(io.BytesIO(parquet_bytes))
