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

    # An hour counts as having measurable precipitation at or above this
    # amount (inches). 0.01" is the smallest measurable amount and the most
    # common one reported; traces are reported as "T", which the summarizer
    # coerces to NaN, so they never count.
    PRECIP_MEASURABLE_THRESHOLD_IN = 0.01

    # Precipitation types, most significant first. When an hour's wxcodes
    # match more than one (e.g. a thunderstorm with rain), the first match
    # in this list wins.
    PRECIP_TYPES = [
        'Thunderstorm', 'Freezing', 'Snow/Ice', 'Rain', 'Drizzle', 'Other / Unspecified']

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

    def _classify_precip_type(self, wxcodes: str) -> str:
        """Classify an hour's present-weather codes into a precipitation type.

        wxcodes is a space-joined string of raw METAR present-weather groups
        (e.g. "-RA BR", "+TSRA", "SN FZFG"). Each token is stripped of its
        intensity prefix (+/-) and the "in the vicinity" prefix (VC), then
        matched against known phenomenon codes; unrelated codes such as BR
        (mist) or FG (fog) don't match anything. When multiple precipitation
        types are present, PRECIP_TYPES' order decides which one wins.

        Returns 'Other / Unspecified' if wxcodes is empty (some automated
        stations report a measurable amount from their rain gauge (p01i)
        without ever sending a present-weather code for it) or if wxcodes is
        present but matches no known type (this covers UP, METAR's own
        "unknown precipitation" code).
        """
        if not wxcodes:
            return 'Other / Unspecified'

        types_present = set()
        for token in wxcodes.split():
            t = token[1:] if token[:1] in ('+', '-') else token
            if t.startswith('VC'):
                t = t[2:]

            if 'TS' in t:
                types_present.add('Thunderstorm')
            if 'FZ' in t and ('RA' in t or 'DZ' in t):
                types_present.add('Freezing')
            if any(code in t for code in ('SN', 'SG', 'PL', 'IC', 'GR', 'GS')):
                types_present.add('Snow/Ice')
            if 'RA' in t and 'FZ' not in t:
                types_present.add('Rain')
            if 'DZ' in t and 'FZ' not in t:
                types_present.add('Drizzle')
            if 'UP' in t:
                types_present.add('Other / Unspecified')

        for precip_type in self.PRECIP_TYPES:
            if precip_type in types_present:
                return precip_type
        return 'Other / Unspecified'


    def _select(self, month: int | None):
        """Rows and grouping for one view of the data.

        With a month, returns that month's rows grouped by UTC hour of day
        (the hourly view). With month=None, returns all rows grouped by
        calendar month, pooling every hour of the day (the year-round view).

        Returns:
            (df, group_key) for use with df.groupby(group_key)
        """
        df = self.hourly_summary
        if month is None:
            return df, df.index.month
        df = df.loc[df.index.month == month]
        return df, df.index.hour

    def _condition_statistics(self, month: int | None) -> pd.DataFrame:
        """Fraction of each flight condition per group (see _select)."""
        df, group_key = self._select(month)

        # Hours without a visibility report (e.g. an AUTO station whose sensor
        # is out) can't be classified: NaN fails every threshold below and
        # would land in LIFR. Leave them out so they don't count as anything.
        has_visibility = df['vsby'].notna()
        df, group_key = df.loc[has_visibility].copy(), group_key[has_visibility]

        # Classify each row based on pre-computed ceiling and visibility
        # (the summarizer already found the minimum ceiling and visibility for each hour)
        df['Sky Condition'] = df.apply(
            lambda row: self._classify_flight_condition(row['ceiling'], row['vsby']),
            axis=1
        )

        # Count how many times each flight condition occurred within each group
        result = (df.groupby(group_key)['Sky Condition']
                  .value_counts().unstack().fillna(0))

        # Convert raw counts into percentages
        result = result.apply(lambda row: row / row.sum(), axis=1)

        result = result.rename({r.value: r.name for r in FlightCondition}, axis=1)

        # Ensure all flight condition columns exist (add missing ones with zeros)
        for condition in ['VFR', 'MVFR', 'IFR', 'LIFR']:
            if condition not in result.columns:
                result[condition] = 0.0

        # Reverse column order so VFR is on bottom (plotly stacks left to right)
        result = result[['VFR', 'MVFR', 'IFR', 'LIFR']]
        result.attrs['airport'] = self.airport_code
        return result

    def get_hourly_statistics(self, month: int) -> pd.DataFrame:
        """Flight condition fractions per UTC hour of day for one month."""
        hourly = self._condition_statistics(month)
        hourly.index = hourly.index.rename('UTC hour')
        hourly.attrs['month'] = month
        return hourly

    def get_monthly_statistics(self) -> pd.DataFrame:
        """Flight condition fractions per calendar month, pooling all hours
        of the day together."""
        monthly = self._condition_statistics(None)
        monthly.index = monthly.index.rename('Month')
        return monthly

    def get_wind_statistics(self, month: int | None = None) -> dict | None:
        """Wind distributions per group: per UTC hour for the given month, or
        per calendar month if month is None (see _select).

        Returns None if there's no wind data for the selection; otherwise a
        dict with:
            speed_bins: ordered list of speed bin labels
            speed: {key: {bin_label: fraction}} over hours with wind data
            gust: {key: {'freq': fraction of hours with a gust,
                         'median': median gust in knots or None,
                         'max': highest gust in knots or None}}
            direction_step: sector width in degrees (20)
            direction_min_kt: winds at or below this speed are excluded from
                the direction distribution
            direction: {key: [18 fractions]}, sector i covering directions
                around i*20 degrees. Fractions are relative to all hours with
                wind data, so hours with light/calm/variable winds make
                columns sum to less than 1.
        """
        df, group_key = self._select(month)
        num_sectors = 360 // self.WIND_DIRECTION_STEP
        half_step = self.WIND_DIRECTION_STEP / 2
        speed = {}
        gust = {}
        direction = {}

        for key, group in df.groupby(group_key):
            speeds = group['sknt'].dropna()
            n = len(speeds)
            if n == 0:
                continue

            speed[int(key)] = {
                label: float(((speeds > low) & (speeds <= high)).sum() / n)
                for label, low, high in self.WIND_SPEED_BINS
            }

            gusts = group['gust'].dropna()
            gust[int(key)] = {
                'freq': float(len(gusts) / n),
                'median': float(gusts.median()) if len(gusts) else None,
                'max': float(gusts.max()) if len(gusts) else None,
            }

            # Directions only count for winds above the threshold with a known
            # direction (calm hours report drct=0, variable wind has no drct)
            directional = group.loc[
                (group['sknt'] > self.WIND_DIRECTION_MIN_KNOTS) & group['drct'].notna(),
                'drct']
            sectors = (((directional + half_step) // self.WIND_DIRECTION_STEP)
                       .astype(int) % num_sectors)
            counts = sectors.value_counts()
            direction[int(key)] = [
                float(counts.get(i, 0) / n) for i in range(num_sectors)
            ]

        if not speed:
            return None

        return {
            'speed_bins': [label for label, _, _ in self.WIND_SPEED_BINS],
            'speed': speed,
            'gust': gust,
            'direction_step': self.WIND_DIRECTION_STEP,
            'direction_min_kt': self.WIND_DIRECTION_MIN_KNOTS,
            'direction': direction,
        }

    def get_temperature_statistics(self, month: int | None = None) -> dict | None:
        """Temperature/dewpoint distributions per group: per UTC hour for the
        given month, or per calendar month if month is None (see _select).

        A percentile band (rather than a single average) is used because
        conditions vary considerably day to day even at a fixed hour.

        Returns None if there's no temperature data for the selection;
        otherwise a dict with 'periods': {key: {
            'temp_p10'/'temp_median'/'temp_p90': degrees Fahrenheit,
            'dewpoint_p10'/'dewpoint_median'/'dewpoint_p90': degrees Fahrenheit or None,
        }}
        """
        df, group_key = self._select(month)
        periods = {}

        for key, group in df.groupby(group_key):
            temps = group['tmpf'].dropna()
            if len(temps) == 0:
                continue

            entry = {
                'temp_p10': float(temps.quantile(0.1)),
                'temp_median': float(temps.median()),
                'temp_p90': float(temps.quantile(0.9)),
            }

            dewpoints = group['dwpf'].dropna()
            has_dewpoints = len(dewpoints) > 0
            entry['dewpoint_p10'] = float(dewpoints.quantile(0.1)) if has_dewpoints else None
            entry['dewpoint_median'] = float(dewpoints.median()) if has_dewpoints else None
            entry['dewpoint_p90'] = float(dewpoints.quantile(0.9)) if has_dewpoints else None

            periods[int(key)] = entry

        if not periods:
            return None

        return {'periods': periods}

    def reports_precipitation_amounts(self) -> bool:
        """Whether this station reports hourly precipitation amounts (p01i).

        Only US METARs carry the amount (the "Pxxxx" remark), and some US
        stations (e.g. many AWOS sites) don't either. IEM reports 0 rather
        than empty for stations without it, so "no data" looks the same as
        "no precipitation". Checking the whole record rather than the
        selected month tells them apart: a station that measures
        precipitation reports a nonzero amount at some point in several
        years, while a dry month at such a station still gets a chart.
        """
        return bool((self.hourly_summary['p01i'] > 0).any())

    def get_precipitation_statistics(self, month: int | None = None) -> dict | None:
        """Precipitation frequency per group: per UTC hour for the given
        month, or per calendar month if month is None (see _select).

        Returns None if the station doesn't report precipitation amounts
        (see reports_precipitation_amounts); otherwise a dict with:
            threshold_in: precipitation amounts below this (inches) don't
                count as measurable
            types: ordered list of precipitation type labels
            periods: {key: {
                'freq': fraction of hours with measurable precipitation,
                'count': number of hours with measurable precipitation,
                'median_in': median amount on hours with precipitation, or None,
                'type_freq': {type: fraction of all hours classified as that
                    type}, summing to 'freq' (each measurable-precipitation
                    hour is classified as exactly one type),
                'type_count': {type: number of hours classified as that
                    type}, summing to 'count',
            }}
        """
        if not self.reports_precipitation_amounts():
            return None

        df, group_key = self._select(month)
        periods = {}

        for key, group in df.groupby(group_key):
            n = len(group)
            if n == 0:
                continue

            is_measurable = group['p01i'] >= self.PRECIP_MEASURABLE_THRESHOLD_IN
            measurable = group.loc[is_measurable, 'p01i']

            types = group.loc[is_measurable, 'wxcodes'].apply(self._classify_precip_type)
            type_counts = types.value_counts()

            periods[int(key)] = {
                'freq': float(len(measurable) / n),
                'count': int(len(measurable)),
                'median_in': float(measurable.median()) if len(measurable) else None,
                'type_freq': {t: float(type_counts.get(t, 0) / n) for t in self.PRECIP_TYPES},
                'type_count': {t: int(type_counts.get(t, 0)) for t in self.PRECIP_TYPES},
            }

        return {
            'threshold_in': self.PRECIP_MEASURABLE_THRESHOLD_IN,
            'types': self.PRECIP_TYPES,
            'periods': periods,
        }
