#!/usr/bin/env python3
"""
Download sample IEM METAR data for testing.

This script downloads 37 months of data for a specified airport
and saves it as a gzip-compressed CSV file in the tests/data directory.

Usage: python download_samples.py KPAO
"""
import argparse
import gzip
import sys
from pathlib import Path

# Add parent directory to path to import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.cache import NoOpCache
from lib.raw_metar_retriever import RawMetarRetriever


def main():
    parser = argparse.ArgumentParser(
        description='Download sample METAR data for testing'
    )
    parser.add_argument(
        'airport',
        help='Airport code to download (e.g., KPAO)'
    )
    args = parser.parse_args()

    # Create a no-op cache that always fetches fresh data
    cache = NoOpCache()
    retriever = RawMetarRetriever(cache)
    output_path = Path(__file__).parent / f'{args.airport.upper()}.csv.gz'

    print(f"Downloading {RawMetarRetriever.NUM_MONTHS} months of METAR data for {args.airport}")

    try:
        # Get raw data using the retriever
        raw_data = retriever.get(args.airport)

        # Save as gzip-compressed CSV
        with gzip.open(output_path, 'wb') as f:
            f.write(raw_data)

        print(f"Saved to {output_path} ({len(raw_data):,} bytes)")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
