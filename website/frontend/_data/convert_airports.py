#!/usr/bin/env python3
"""
Convert OurAirports CSV data to simplified JSON format for web autocomplete.

Filters airports with ICAO codes and exports to JSON with fields:
icao, iata, name, city, country
"""

import pandas as pd
from pathlib import Path

# Paths
INPUT_CSV = './airports.csv.gz'
OUTPUT_JSON = Path(__file__).parent / '../assets/data/airports.json.gz'


def convert_airports():
    """Load CSV, filter, and export to JSON."""

    # Read CSV
    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV, usecols=[
        'icao_code', 'iata_code', 'name', 'municipality', 'iso_country'
    ])

    # Rename columns to match output format
    df = df.rename(columns={
        'icao_code': 'icao',
        'iata_code': 'iata',
        'municipality': 'city',
        'iso_country': 'country'
    })

    # Must have ICAO code, name and city
    df = df[df['icao'].notna() & (df['icao'] != '')]
    df = df[df['name'].notna() & (df['name'] != '')]
    df = df[df['city'].notna() & (df['city'] != '')]

    # Strip whitespace
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # Replace empty IATA codes with None
    df['iata'] = df['iata'].replace('', None)

    # Remove duplicates by ICAO (keep first)
    df = df.drop_duplicates(subset='icao', keep='first')

    # Sort by ICAO code
    df = df.sort_values('icao')

    # Write JSON
    print(f"Writing {len(df)} airports to {OUTPUT_JSON}...")
    df.to_json(OUTPUT_JSON, orient='records', force_ascii=False, indent=2)

    print(f"Done! Generated {OUTPUT_JSON.stat().st_size / 1024 / 1024:.1f} MB JSON file")


if __name__ == '__main__':
    convert_airports()
