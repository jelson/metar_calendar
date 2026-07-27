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
    # Wind speed bins: (label, min knots exclusive, max knots inclusive).
    WIND_SPEED_BINS = [
        ('0-3 kt', -1, 3),
        ('4-8 kt', 3, 8),
        ('9-13 kt', 8, 13),
        ('14-18 kt', 13, 18),
        ('>18 kt', 18, float('inf')),
    ]

    # Wind directions are binned into 18 sectors of 20 degrees each,
    # centered on 000, 020, ..., 340.
    WIND_DIRECTION_STEP = 20

    # Winds at or below this speed are excluded from the direction
    # distribution: light winds meander and their direction is mostly noise.
    WIND_DIRECTION_MIN_KNOTS = 5

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

    def get_hourly_wind_statistics(self, month: int) -> dict:
        """Compute per-UTC-hour wind distributions for the given month.

        Returns a dict with:
            speed_bins: ordered list of speed bin labels
            hourly_speed: {hour: {bin_label: fraction}} over hours with wind data
            hourly_gust: {hour: {'freq': fraction of hours with a gust,
                                 'median': median gust in knots or None,
                                 'max': highest gust in knots or None}}
            direction_step: sector width in degrees (20)
            direction_min_kt: winds at or below this speed are excluded from
                the direction distribution
            hourly_direction: {hour: [18 fractions]}, sector i covering
                directions around i*20 degrees. Fractions are relative to all
                hours with wind data, so hours with light/calm/variable winds
                make columns sum to less than 1.
        """
        if 'sknt' not in self.hourly_summary.columns:
            raise ValueError(
                'Cached summary has no wind data; clear the cache to regenerate')

        df = self.hourly_summary
        df = df.loc[df.index.month == month]

        num_sectors = 360 // self.WIND_DIRECTION_STEP
        hourly_speed = {}
        hourly_gust = {}
        hourly_direction = {}

        for hour, group in df.groupby(df.index.hour):
            speeds = group['sknt'].dropna()
            n = len(speeds)
            if n == 0:
                continue

            hourly_speed[int(hour)] = {
                label: float(((speeds > low) & (speeds <= high)).sum() / n)
                for label, low, high in self.WIND_SPEED_BINS
            }

            gusts = group['gust'].dropna()
            hourly_gust[int(hour)] = {
                'freq': float(len(gusts) / n),
                'median': float(gusts.median()) if len(gusts) else None,
                'max': float(gusts.max()) if len(gusts) else None,
            }

            # Directions only count for winds above the threshold with a known
            # direction (calm hours report drct=0, variable wind has no drct)
            directional = group.loc[
                (group['sknt'] > self.WIND_DIRECTION_MIN_KNOTS) & group['drct'].notna(),
                'drct']
            half_step = self.WIND_DIRECTION_STEP / 2
            sectors = (((directional + half_step) // self.WIND_DIRECTION_STEP)
                       .astype(int) % num_sectors)
            counts = sectors.value_counts()
            hourly_direction[int(hour)] = [
                float(counts.get(i, 0) / n) for i in range(num_sectors)
            ]

        return {
            'speed_bins': [label for label, _, _ in self.WIND_SPEED_BINS],
            'hourly_speed': hourly_speed,
            'hourly_gust': hourly_gust,
            'direction_step': self.WIND_DIRECTION_STEP,
            'direction_min_kt': self.WIND_DIRECTION_MIN_KNOTS,
            'hourly_direction': hourly_direction,
        }
