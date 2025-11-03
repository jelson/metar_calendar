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

        Args:
            airport: Airport code (normalized, e.g., 'KSFO', 'KPAO')

        Returns:
            DataFrame indexed by hour with columns: vsby, ceiling
        """
        # Get raw CSV data
        raw_csv = self.retriever.get(airport)

        # Parse CSV into dataframe - only read columns we need for performance
        cols_needed = ['valid', 'vsby', 'skyc1', 'skyl1', 'skyc2', 'skyl2',
                       'skyc3', 'skyl3', 'skyc4', 'skyl4']
        df = pd.read_csv(io.StringIO(raw_csv.decode('utf8', errors='ignore')),
                         usecols=cols_needed)

        # Rename and parse date column
        df = df.rename({'valid': 'date'}, axis=1)
        df = df.sort_values('date').reset_index(drop=True)
        df['date'] = df['date'].apply(lambda d: datetime.datetime.strptime(
            d, "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC))

        # Convert visibility and sky levels to numeric (coerce errors to NaN)
        for col in ['vsby', 'skyl1', 'skyl2', 'skyl3', 'skyl4']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert sky condition codes to strings to avoid any mixed type issues
        for col in ['skyc1', 'skyc2', 'skyc3', 'skyc4']:
            if col in df.columns:
                df[col] = df[col].astype(str)

        say(f'Fetched {len(df)} rows from {df["date"].min()} to {df["date"].max()}')

        # Calculate ceiling for each observation
        df['ceiling'] = df.apply(self._calculate_ceiling, axis=1)

        # Group by hour and find minimum visibility and ceiling
        grouping = df['date'].dt.floor('1h')
        hourly = df.groupby(grouping).agg({
            'vsby': 'min',
            'ceiling': 'min'
        })

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
        cache_key = f"{airport}_summarized.parquet"

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
