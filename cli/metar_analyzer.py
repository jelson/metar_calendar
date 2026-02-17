#!/usr/bin/env python3
import argparse
import appdirs
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.analyzer import METARAnalyzer  # noqa: E402
from lib.storage import LocalFileStorage  # noqa: E402
from lib.sun_utils import get_daylight_utc_hours  # noqa: E402
from lib.timezone_utils import get_utc_offsets_for_month  # noqa: E402
from lib.visualizer import METARVisualizer  # noqa: E402

METADATA_PATH = Path(__file__).parent / '../website/backend/data/airport_metadata.parquet'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-a', '--airport',
        help='Airport ICAO code (e.g., KACV)',
        type=str,
        required=True,
    )
    parser.add_argument(
        '-m', '--month',
        help='Month number to plot',
        required=True,
        type=int,
        choices=range(1, 13),
        metavar="<1-12>",
    )
    parser.add_argument(
        '-c', '--chart',
        help='Generate PNG chart to <airport>-<month>.png',
        action='store_true',
    )
    parser.add_argument(
        '-d', '--directory',
        help='Directory for output files (default: current directory)',
        type=str,
        default='.',
    )
    parser.add_argument(
        '-t', '--table',
        help='Print hourly statistics table to stdout',
        action='store_true',
    )
    args = parser.parse_args()

    # Create storage with local file storage
    cache_dir = appdirs.user_cache_dir("metar_calendar")
    storage = LocalFileStorage(cache_dir)

    # Require at least one output option
    if not args.table and not args.chart:
        parser.error('At least one output option required: -t/--table or -c/--chart')

    analyzer = METARAnalyzer(args.airport, storage)
    hourly = analyzer.get_hourly_statistics(args.month)

    if args.table:
        print(METARVisualizer.format_table(hourly))

    if args.chart:
        # Look up timezone and location metadata for the airport.
        # The metadata parquet is keyed by IEM query code (e.g., "SMO"),
        # but the user may provide the ICAO code (e.g., "KSMO"). Try both.
        metadata = pd.read_parquet(METADATA_PATH)
        airport_upper = args.airport.upper()
        meta_key = None
        if airport_upper in metadata.index:
            meta_key = airport_upper
        elif len(airport_upper) == 4 and airport_upper.startswith('K'):
            stripped = airport_upper[1:]
            if stripped in metadata.index:
                meta_key = stripped

        utc_offsets = []
        daylight_utc = None
        if meta_key is not None:
            row = metadata.loc[meta_key]
            utc_offsets = get_utc_offsets_for_month(row.get('tz'), args.month)
            daylight_utc = get_daylight_utc_hours(
                row.get('lat'), row.get('lon'), args.month)

        output_filename = f'{airport_upper}-{args.month:02d}.png'
        output_path = os.path.join(args.directory, output_filename)
        png_bytes = METARVisualizer.generate_png(hourly, utc_offsets, daylight_utc)
        with open(output_path, 'wb') as f:
            f.write(png_bytes)


if __name__ == '__main__':
    main()
