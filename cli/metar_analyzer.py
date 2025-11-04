#!/usr/bin/env python3
import argparse
import appdirs
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.analyzer import METARAnalyzer  # noqa: E402
from lib.storage import LocalFileStorage  # noqa: E402
from lib.visualizer import METARVisualizer  # noqa: E402


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
        output_filename = f'{args.airport.upper()}-{args.month:02d}.png'
        output_path = os.path.join(args.directory, output_filename)
        png_bytes = METARVisualizer.generate_png(hourly)
        with open(output_path, 'wb') as f:
            f.write(png_bytes)


if __name__ == '__main__':
    main()
