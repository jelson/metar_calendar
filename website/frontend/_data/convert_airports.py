#!/usr/bin/env python3
"""
Convert OurAirports CSV data to simplified JSON format for web autocomplete.

Filters airports to only include those with METAR data available from IEM.
Cross-references OurAirports data with IEM station list.

Output fields: icao, iata, name, city, country, query
- query: the identifier to use when querying IEM API (ICAO or IATA)
"""

import pandas as pd
from pathlib import Path
import requests

# Paths
INPUT_CSV = './airports.csv.gz'
OUTPUT_JSON = Path(__file__).parent / '../assets/data/airports.json'

# IEM station list URL
IEM_STATIONS_URL = 'https://mesonet.agron.iastate.edu/sites/networks.php?network=_ALL_&format=csv&nohtml=on'


def fetch_iem_stations():
    """Download list of all IEM weather stations."""
    print(f"Fetching IEM station list from {IEM_STATIONS_URL}...")
    response = requests.get(IEM_STATIONS_URL, timeout=30)
    response.raise_for_status()

    # Parse CSV from response
    from io import StringIO
    iem_df = pd.read_csv(StringIO(response.text))

    print(f"Found {len(iem_df)} IEM stations")

    # Extract station IDs (they use 'stid' column for station identifier)
    # These are typically ICAO codes
    station_ids = set(iem_df['stid'].dropna().str.strip().str.upper())

    print(f"Extracted {len(station_ids)} unique station IDs")
    return station_ids


def convert_airports():
    """Load CSV, cross-reference with IEM stations, and export to JSON."""

    # Fetch IEM stations first
    iem_stations = fetch_iem_stations()

    # Read OurAirports CSV
    print(f"\nReading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV, usecols=[
        'icao_code', 'iata_code', 'name', 'municipality', 'iso_country'
    ])

    print(f"Total airports in OurAirports database: {len(df)}")

    # Rename columns to match output format
    df = df.rename(columns={
        'icao_code': 'icao',
        'iata_code': 'iata',
        'municipality': 'city',
        'iso_country': 'country'
    })

    # Strip whitespace
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # Replace empty strings with None
    df = df.replace('', None)

    # Cross-reference with IEM stations
    # Keep airports where ICAO OR IATA matches an IEM station ID
    # Also track which identifier to use for queries
    df['icao_upper'] = df['icao'].str.upper()
    df['iata_upper'] = df['iata'].str.upper()

    # Determine which identifier matches IEM (prefer ICAO)
    df['icao_in_iem'] = df['icao_upper'].isin(iem_stations)
    df['iata_in_iem'] = df['iata_upper'].isin(iem_stations)

    # Filter: keep only airports with at least one match
    df = df[df['icao_in_iem'] | df['iata_in_iem']]

    # Set 'query' field: use ICAO if it's in IEM, otherwise use IATA
    df['query'] = df.apply(
        lambda row: row['icao'] if row['icao_in_iem'] else row['iata'],
        axis=1
    )

    # Drop temporary columns
    df = df.drop(columns=['icao_upper', 'iata_upper', 'icao_in_iem', 'iata_in_iem'])

    print(f"Airports with IEM METAR data: {len(df)}")

    # Remove duplicates by ICAO (keep first)
    original_count = len(df)
    df = df.drop_duplicates(subset='icao', keep='first')
    if len(df) < original_count:
        print(f"Removed {original_count - len(df)} duplicates")

    # Sort by ICAO code
    df = df.sort_values('icao')

    # Write JSON
    print(f"\nWriting {len(df)} airports to {OUTPUT_JSON}...")
    df.to_json(OUTPUT_JSON, orient='records', force_ascii=False, indent=2)

    print(f"Done! Generated {OUTPUT_JSON.stat().st_size / 1024 / 1024:.1f} MB JSON file")


if __name__ == '__main__':
    convert_airports()
