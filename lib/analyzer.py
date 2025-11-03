import pandas as pd
from enum import IntEnum

from lib.cache import Cache
from lib.metar_summarizer import MetarSummarizer
from lib.storage import Storage


class FlightCondition(IntEnum):
    LIFR = 1
    IFR = 2
    MVFR = 3
    VFR = 4


class METARAnalyzer:
    def __init__(self, airport_code: str, storage: Storage):
        self.airport_code = airport_code.upper().strip()
        cache = Cache(storage)
        self.summarizer = MetarSummarizer(cache)
        self.hourly_summary = self.summarizer.get(airport_code)

    def _classify_flight_condition(self, ceiling: float, vsby: float) -> FlightCondition:
        """Classify flight condition based on ceiling and visibility."""
        if ceiling >= 3000 and vsby >= 5:
            return FlightCondition.VFR
        if ceiling >= 1000 and vsby >= 3:
            return FlightCondition.MVFR
        if ceiling >= 500 and vsby >= 1:
            return FlightCondition.IFR
        return FlightCondition.LIFR

    def get_hourly_statistics(self, month: int) -> pd.DataFrame:
        # Filter to requested month
        df = self.hourly_summary
        df = df.loc[df.index.month == month].copy()

        # Classify each hour based on pre-computed ceiling and visibility
        # (the summarizer already found the minimum ceiling and visibility for each hour)
        df['Sky Condition'] = df.apply(
            lambda row: self._classify_flight_condition(row['ceiling'], row['vsby']),
            axis=1
        )

        # For every one of the 24 hours, count how many times a flight
        # condition occurred during that hour
        hourly = (df.groupby(df.index.hour)['Sky Condition']
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

        hourly.attrs['airport'] = self.airport_code
        hourly.attrs['month'] = month

        return hourly
