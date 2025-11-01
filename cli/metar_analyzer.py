#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.analyzer import METARAnalyzer  # noqa: E402
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
        '-o', '--output',
        help='Output filename; default is <airport>-<month>.png',
        type=str,
    )
    parser.add_argument(
        '--print-table',
        help='Print hourly statistics table to stdout',
        action='store_true',
    )
    args = parser.parse_args()

    analyzer = METARAnalyzer(args.airport)
    hourly = analyzer.get_hourly_statistics(args.month)

    if args.print_table:
        print(METARVisualizer.format_table(hourly))

    output_path = args.output or f'{args.airport.upper()}-{args.month:02d}.png'
    png_bytes = METARVisualizer.generate_png(hourly)
    with open(output_path, 'wb') as f:
        f.write(png_bytes)


if __name__ == '__main__':
    main()
