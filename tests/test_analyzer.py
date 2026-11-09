import pandas as pd
import pytest
import tempfile
from unittest.mock import patch

from lib.analyzer import METARAnalyzer, FlightCondition
from lib.storage import LocalFileStorage
from .test_utils import FLIGHT_CONDITIONS, get_test_airports, mock_requests_get


class TestFlightCondition:
    def test_enum_values(self):
        # FlightCondition is an IntEnum with these values
        assert FlightCondition.LIFR == 1
        assert FlightCondition.IFR == 2
        assert FlightCondition.MVFR == 3
        assert FlightCondition.VFR == 4

    def test_enum_names(self):
        assert FlightCondition.LIFR.name == 'LIFR'
        assert FlightCondition.IFR.name == 'IFR'
        assert FlightCondition.MVFR.name == 'MVFR'
        assert FlightCondition.VFR.name == 'VFR'


class TestMETARAnalyzer:
    @pytest.fixture
    def storage(self):
        """Create storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalFileStorage(tmpdir)

    @patch('lib.raw_metar_retriever.requests.get')
    def test_initialization(self, mock_requests, storage):
        """Test that METARAnalyzer initializes and fetches summary data."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        assert analyzer.airport_code == 'KPAO'
        assert analyzer.summarizer is not None
        assert isinstance(analyzer.hourly_summary, pd.DataFrame)
        assert len(analyzer.hourly_summary) > 0

    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    def test_hourly_stats_structure(self, mock_requests, storage, airport):
        """Test that get_hourly_statistics returns proper DataFrame structure."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)

        # Test all 12 months
        for month in range(1, 13):
            result = analyzer.get_hourly_statistics(month)

            # Should return a DataFrame with hours as index
            assert isinstance(result, pd.DataFrame)
            assert len(result) <= 24  # At most 24 hours

            # All four columns should exist even if some are 0
            assert all(col in result.columns for col in FLIGHT_CONDITIONS)

            # Check attributes are set
            assert result.attrs.get('airport') == airport
            assert result.attrs.get('month') == month

    @patch('lib.raw_metar_retriever.requests.get')
    def test_classification_logic(self, mock_requests, storage):
        """Test that flight conditions are properly classified."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        # VFR: ceiling >= 3000 AND visibility >= 5
        assert analyzer._classify_flight_condition(5000, 10) == FlightCondition.VFR
        assert analyzer._classify_flight_condition(3000, 5) == FlightCondition.VFR  # Boundary

        # VFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(2999, 10) == FlightCondition.MVFR  # Ceiling just under VFR

        # VFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 4.9) == FlightCondition.MVFR  # Visibility just under VFR

        # MVFR: ceiling >= 1000 AND visibility >= 3
        assert analyzer._classify_flight_condition(2000, 4) == FlightCondition.MVFR
        assert analyzer._classify_flight_condition(1000, 3) == FlightCondition.MVFR  # Boundary

        # MVFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(999, 10) == FlightCondition.IFR  # Ceiling just under MVFR

        # MVFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 2.9) == FlightCondition.IFR  # Visibility just under MVFR

        # IFR: ceiling >= 500 AND visibility >= 1
        assert analyzer._classify_flight_condition(800, 2) == FlightCondition.IFR
        assert analyzer._classify_flight_condition(500, 1) == FlightCondition.IFR  # Boundary

        # IFR limited by ceiling (visibility good but ceiling too low)
        assert analyzer._classify_flight_condition(499, 10) == FlightCondition.LIFR  # Ceiling just under IFR

        # IFR limited by visibility (ceiling good but visibility too low)
        assert analyzer._classify_flight_condition(5000, 0.9) == FlightCondition.LIFR  # Visibility just under IFR

        # LIFR: ceiling < 500 OR visibility < 1
        assert analyzer._classify_flight_condition(300, 0.5) == FlightCondition.LIFR
        assert analyzer._classify_flight_condition(100, 0.25) == FlightCondition.LIFR  # Very low ceiling
        assert analyzer._classify_flight_condition(200, 10) == FlightCondition.LIFR  # Low ceiling, good visibility
        assert analyzer._classify_flight_condition(5000, 0.5) == FlightCondition.LIFR  # Good ceiling, low visibility

    @patch('lib.raw_metar_retriever.requests.get')
    def test_percentages_sum_to_one(self, mock_requests, storage):
        """Test that percentages for each hour sum to 1."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)
        result = analyzer.get_hourly_statistics(1)

        # Each row should sum to 1.0 (100%)
        for hour, row in result.iterrows():
            total = sum(row[condition] for condition in FLIGHT_CONDITIONS)
            assert abs(total - 1.0) < 0.001, f"Hour {hour} sums to {total}, not 1.0"

    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    def test_monthly_stats_structure(self, mock_requests, storage, airport):
        """Test that get_monthly_statistics returns proper DataFrame structure."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)
        result = analyzer.get_monthly_statistics()

        assert isinstance(result, pd.DataFrame)
        assert len(result) <= 12  # At most 12 months
        assert all(month in range(1, 13) for month in result.index)
        assert all(col in result.columns for col in FLIGHT_CONDITIONS)
        assert result.attrs.get('airport') == airport

    @patch('lib.raw_metar_retriever.requests.get')
    def test_monthly_percentages_sum_to_one(self, mock_requests, storage):
        """Test that percentages for each month sum to 1."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)
        result = analyzer.get_monthly_statistics()

        for month, row in result.iterrows():
            total = sum(row[condition] for condition in FLIGHT_CONDITIONS)
            assert abs(total - 1.0) < 0.001, f"Month {month} sums to {total}, not 1.0"

    # The weather stats methods share one code path for both views: with a
    # month they're keyed by UTC hour (0-23), with month=None by calendar
    # month (1-12). Structure tests run against both.
    VIEWS = [
        pytest.param(6, range(0, 24), id='hourly'),
        pytest.param(None, range(1, 13), id='monthly'),
    ]

    def _make_summary_parquet(self, storage, airport, df):
        """Store a pre-built hourly summary in the cache for an airport."""
        import io
        buffer = io.BytesIO()
        df.to_parquet(buffer)
        storage.put(f'{airport}.summarized.v4.parquet', buffer.getvalue())

    @pytest.mark.parametrize("month,valid_keys", VIEWS)
    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    def test_wind_stats_structure(self, mock_requests, storage, airport, month, valid_keys):
        """Test that get_wind_statistics returns a well-formed result."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)
        result = analyzer.get_wind_statistics(month)

        assert result['speed_bins'] == [
            '0-3 kt', '4-8 kt', '9-13 kt', '14-18 kt', '>18 kt']
        assert result['direction_step'] == 20

        assert len(result['speed']) > 0
        for key, bins in result['speed'].items():
            assert key in valid_keys
            # Speed bins cover all speeds, so fractions sum to 1
            assert abs(sum(bins.values()) - 1.0) < 0.001

        for key, gust in result['gust'].items():
            assert 0 <= gust['freq'] <= 1
            if gust['freq'] > 0:
                assert 0 < gust['median'] <= gust['max']

        for key, sectors in result['direction'].items():
            assert len(sectors) == 18
            # Calm/variable winds aren't directional, so sums can be below 1
            assert sum(sectors) <= 1.001

    def test_wind_stats_calm_and_direction_wrapping(self, storage):
        """Calm/light hours have no direction; 355 and 005 both bin to 000."""
        index = pd.DatetimeIndex([
            f'2025-06-{day:02d} 10:00' for day in range(1, 7)], tz='UTC')
        df = pd.DataFrame({
            'vsby': [10.0] * 6,
            'ceiling': [10000.0] * 6,
            #        calm  light east  north-ish  north-ish  south  no data
            'sknt': [0.0,  4.0,        10.0,      12.0,      22.0,  float('nan')],
            'drct': [0.0,  90.0,       355.0,     5.0,       180.0, float('nan')],
            'gust': [float('nan'), float('nan'), float('nan'), 25.0,
                     float('nan'), float('nan')],
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        result = analyzer.get_wind_statistics(6)

        # 5 hours have wind data (the NaN hour is excluded). sknt values are
        # 0, 4, 10, 12, 22; 10 and 12 both fall in the 9-13 kt bucket.
        speed = result['speed'][10]
        assert speed['0-3 kt'] == 0.2
        assert speed['4-8 kt'] == 0.2
        assert speed['9-13 kt'] == pytest.approx(0.4)
        assert speed['14-18 kt'] == 0.0
        assert speed['>18 kt'] == 0.2

        gust = result['gust'][10]
        assert gust['freq'] == 0.2
        assert gust['median'] == 25.0
        assert gust['max'] == 25.0

        # 355 and 005 are both within 5 degrees of north: same sector.
        # Calm and light (<= 5 kt) winds must not count towards any sector.
        sectors = result['direction'][10]
        assert sectors[0] == pytest.approx(0.4)  # 355 and 005
        assert sectors[5] == 0  # the 4 kt easterly (090) is ignored
        assert sectors[9] == pytest.approx(0.2)  # 180
        # calm, light and missing don't contribute
        assert sum(sectors) == pytest.approx(0.6)

        # The year-round view pools the same rows under their month (June)
        assert analyzer.get_wind_statistics()['speed'] == {6: speed}

    @pytest.mark.parametrize("month,valid_keys", VIEWS)
    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    def test_temperature_stats_structure(self, mock_requests, storage, airport, month, valid_keys):
        """Test that get_temperature_statistics returns a well-formed result."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)
        result = analyzer.get_temperature_statistics(month)

        assert len(result['periods']) > 0
        for key, stats in result['periods'].items():
            assert key in valid_keys
            assert stats['temp_p10'] <= stats['temp_median'] <= stats['temp_p90']
            if stats['dewpoint_median'] is not None:
                assert stats['dewpoint_p10'] <= stats['dewpoint_median'] <= stats['dewpoint_p90']

    def test_temperature_stats_synthetic(self, storage):
        """Percentiles are computed correctly from the underlying samples."""
        index = pd.DatetimeIndex([
            f'2025-06-{day:02d} 10:00' for day in range(1, 11)], tz='UTC')
        temps = [50.0, 52.0, 54.0, 56.0, 58.0, 60.0, 62.0, 64.0, 66.0, 68.0]
        dewpoints = [t - 10 for t in temps]
        df = pd.DataFrame({
            'vsby': [10.0] * 10,
            'ceiling': [10000.0] * 10,
            'tmpf': temps,
            'dwpf': dewpoints,
            'p01i': [0.0] * 10,
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        result = analyzer.get_temperature_statistics(6)

        stats = result['periods'][10]
        assert stats['temp_median'] == pytest.approx(59.0)
        assert stats['temp_p10'] == pytest.approx(51.8)
        assert stats['temp_p90'] == pytest.approx(66.2)
        assert stats['dewpoint_median'] == pytest.approx(49.0)

    @pytest.mark.parametrize("month,valid_keys", VIEWS)
    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    def test_precipitation_stats_structure(
            self, mock_requests, storage, airport, month, valid_keys):
        """Test that get_precipitation_statistics returns a well-formed result."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer(airport, storage)
        result = analyzer.get_precipitation_statistics(month)

        # Some test stations (e.g. KPAO) don't report precipitation amounts
        if not analyzer.reports_precipitation_amounts():
            assert result is None
            return

        assert result['threshold_in'] == 0.01
        assert result['types'] == [
            'Thunderstorm', 'Freezing', 'Snow/Ice', 'Rain', 'Drizzle', 'Other / Unspecified']
        assert len(result['periods']) > 0
        for key, stats in result['periods'].items():
            assert key in valid_keys
            assert 0 <= stats['freq'] <= 1
            assert stats['count'] >= 0
            if stats['freq'] > 0:
                assert stats['median_in'] > 0
            # Type breakdown always sums to the overall frequency/count
            assert sum(stats['type_freq'].values()) == pytest.approx(stats['freq'])
            assert sum(stats['type_count'].values()) == stats['count']

    def test_precipitation_stats_synthetic(self, storage):
        """Frequency and median only count measurable precipitation."""
        index = pd.DatetimeIndex([
            f'2025-06-{day:02d} 10:00' for day in range(1, 7)], tz='UTC')
        df = pd.DataFrame({
            'vsby': [10.0] * 6,
            'ceiling': [10000.0] * 6,
            'tmpf': [50.0] * 6,
            'dwpf': [40.0] * 6,
            # below threshold, dry, minimum measurable (0.01" counts),
            # measurable, measurable, missing (e.g. a "T" trace report)
            'p01i': [0.005, 0.0, 0.01, 0.10, 0.20, float('nan')],
            'wxcodes': ['-RA', '', '-DZ', '-RA', '+TSRA', ''],
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        result = analyzer.get_precipitation_statistics(6)

        stats = result['periods'][10]
        assert stats['freq'] == pytest.approx(0.5)  # 3 of 6 hours
        assert stats['count'] == 3
        assert stats['median_in'] == pytest.approx(0.10)
        # The three measurable hours are Drizzle (0.01), Rain (0.10) and
        # Thunderstorm (0.20)
        assert stats['type_freq']['Drizzle'] == pytest.approx(1 / 6)
        assert stats['type_freq']['Rain'] == pytest.approx(1 / 6)
        assert stats['type_freq']['Thunderstorm'] == pytest.approx(1 / 6)
        assert stats['type_freq']['Snow/Ice'] == 0.0
        assert stats['type_count']['Drizzle'] == 1
        assert stats['type_count']['Rain'] == 1
        assert stats['type_count']['Thunderstorm'] == 1
        assert stats['type_count']['Snow/Ice'] == 0

    def test_precipitation_stats_none_without_amounts(self, storage):
        """Stations that never report an amount (IEM fills in 0, e.g. outside
        the US) get no precipitation stats, even though wxcodes show rain."""
        index = pd.DatetimeIndex([
            f'2025-{month:02d}-01 10:00' for month in (1, 6)], tz='UTC')
        df = pd.DataFrame({
            'vsby': [10.0] * 2,
            'ceiling': [10000.0] * 2,
            'p01i': [0.0, 0.0],
            'wxcodes': ['-RA', 'RA'],
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        assert not analyzer.reports_precipitation_amounts()
        assert analyzer.get_precipitation_statistics(6) is None
        assert analyzer.get_precipitation_statistics() is None

    def test_precipitation_stats_dry_month_at_reporting_station(self, storage):
        """A dry month at a station that does report amounts still gets
        (all-zero) stats: availability is judged over the whole record."""
        index = pd.DatetimeIndex([
            f'2025-{month:02d}-01 10:00' for month in (1, 6)], tz='UTC')
        df = pd.DataFrame({
            'vsby': [10.0] * 2,
            'ceiling': [10000.0] * 2,
            'p01i': [0.25, 0.0],  # wet January, dry June
            'wxcodes': ['RA', ''],
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        result = analyzer.get_precipitation_statistics(6)
        assert result['periods'][10]['count'] == 0

    def test_wind_and_temperature_stats_none_without_data(self, storage):
        """A selection with no wind or temperature readings returns None."""
        index = pd.DatetimeIndex(['2025-06-01 10:00'], tz='UTC')
        nan = float('nan')
        df = pd.DataFrame({
            'vsby': [10.0], 'ceiling': [10000.0],
            'sknt': [nan], 'gust': [nan], 'drct': [nan],
            'tmpf': [nan], 'dwpf': [nan],
        }, index=index)
        self._make_summary_parquet(storage, 'KTEST', df)

        analyzer = METARAnalyzer('KTEST', storage)
        for month in (6, None):
            assert analyzer.get_wind_statistics(month) is None
            assert analyzer.get_temperature_statistics(month) is None

    @pytest.mark.parametrize("wxcodes,expected", [
        ('', 'Other / Unspecified'),      # no wx code at all, e.g. a gauge-only station
        ('BR', 'Other / Unspecified'),    # mist alone isn't precipitation
        ('-RA', 'Rain'),
        ('-RA BR', 'Rain'),
        ('+RA', 'Rain'),
        ('-DZ', 'Drizzle'),
        ('-SN', 'Snow/Ice'),
        ('SN FZFG', 'Snow/Ice'),          # freezing fog isn't freezing precip
        ('-SN BLSN', 'Snow/Ice'),         # blowing snow still counts as snow
        ('GR', 'Snow/Ice'),               # hail
        ('-FZRA BR', 'Freezing'),
        ('-FZDZ', 'Freezing'),
        ('TS', 'Thunderstorm'),
        ('-TSRA', 'Thunderstorm'),
        ('VCTS -RA', 'Thunderstorm'),     # thunderstorm outranks rain
        ('UP', 'Other / Unspecified'),
        ('UP BR', 'Other / Unspecified'),
    ])
    def test_classify_precip_type(self, wxcodes, expected):
        """Test present-weather code classification with real-world examples."""
        # _classify_precip_type only reads class-level constants, so it's
        # safe to call without fetching any data via __init__
        analyzer = METARAnalyzer.__new__(METARAnalyzer)
        assert analyzer._classify_precip_type(wxcodes) == expected

    @patch('lib.raw_metar_retriever.requests.get')
    def test_multiple_months(self, mock_requests, storage):
        """Test that we can request statistics for different months from same analyzer."""
        mock_requests.side_effect = mock_requests_get

        analyzer = METARAnalyzer('KPAO', storage)

        # Request multiple months
        jan = analyzer.get_hourly_statistics(1)
        jun = analyzer.get_hourly_statistics(6)

        # Both should be valid DataFrames
        assert isinstance(jan, pd.DataFrame)
        assert isinstance(jun, pd.DataFrame)

        # Attributes should reflect the correct month
        assert jan.attrs.get('month') == 1
        assert jun.attrs.get('month') == 6

        # Should not have made additional requests (using cached summary)
        assert mock_requests.call_count == 1
