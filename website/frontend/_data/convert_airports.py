#!/usr/bin/env python3
"""
Convert OurAirports CSV data to simplified JSON format for web autocomplete.

Filters airports to only include those with METAR data available from IEM.
Cross-references OurAirports data with IEM station list.

Output fields: icao, iata, name, city, country, query
- query: the identifier to use when querying IEM API
- Matching priority: 1) ident, 2) icao_code, 3) iata_code, 4) local_code, 5) gps_code
- If no icao_code or iata_code, the matched identifier is used as the display code
"""

import pandas as pd
from pathlib import Path
import requests

# URLs
OURAIRPORTS_URL = 'https://davidmegginson.github.io/ourairports-data/airports.csv'
IEM_STATIONS_URL = 'https://mesonet.agron.iastate.edu/sites/networks.php?network=_ALL_&format=csv&nohtml=on'

# Output path
OUTPUT_JSON = Path(__file__).parent / '../assets/data/airports.json'


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

    # Fetch OurAirports CSV
    print(f"\nFetching OurAirports data from {OURAIRPORTS_URL}...")
    response = requests.get(OURAIRPORTS_URL, timeout=30)
    response.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(response.text), usecols=[
        'ident', 'icao_code', 'iata_code', 'local_code', 'gps_code',
        'name', 'municipality', 'iso_country'
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
    # Priority order: 1) ident, 2) icao, 3) iata, 4) local_code, 5) gps_code
    df['ident_upper'] = df['ident'].str.upper()
    df['icao_upper'] = df['icao'].str.upper()
    df['iata_upper'] = df['iata'].str.upper()
    df['local_upper'] = df['local_code'].str.upper()
    df['gps_upper'] = df['gps_code'].str.upper()

    # Determine which identifier matches IEM
    df['ident_in_iem'] = df['ident_upper'].isin(iem_stations)
    df['icao_in_iem'] = df['icao_upper'].isin(iem_stations)
    df['iata_in_iem'] = df['iata_upper'].isin(iem_stations)
    df['local_in_iem'] = df['local_upper'].isin(iem_stations)
    df['gps_in_iem'] = df['gps_upper'].isin(iem_stations)

    # Filter: keep only airports with at least one match
    df = df[df['ident_in_iem'] | df['icao_in_iem'] | df['iata_in_iem'] |
            df['local_in_iem'] | df['gps_in_iem']]

    # Set 'query' field using priority order: ident > icao > iata > local_code > gps_code
    def determine_query(row):
        if row['ident_in_iem']:
            return row['ident']
        elif row['icao_in_iem']:
            return row['icao']
        elif row['iata_in_iem']:
            return row['iata']
        elif row['local_in_iem']:
            return row['local_code']
        elif row['gps_in_iem']:
            return row['gps_code']
        return None

    df['query'] = df.apply(determine_query, axis=1)

    # If no icao or iata, use the query field as icao for display
    missing_both = df['icao'].isna() & df['iata'].isna()
    df.loc[missing_both, 'icao'] = df.loc[missing_both, 'query']

    # Keep only the columns we need for output
    df = df[['icao', 'iata', 'name', 'city', 'country', 'query']]

    print(f"Airports with IEM METAR data: {len(df)}")

    # Remove duplicates by query (the IEM station identifier - keep first)
    original_count = len(df)
    df = df.drop_duplicates(subset='query', keep='first')
    if len(df) < original_count:
        print(f"Removed {original_count - len(df)} duplicates")

    # Sort by query code
    df = df.sort_values('query')

    # Write JSON
    print(f"\nWriting {len(df)} airports to {OUTPUT_JSON}...")
    df.to_json(OUTPUT_JSON, orient='records', force_ascii=False, indent=2)

    print(f"Done! Generated {OUTPUT_JSON.stat().st_size / 1024 / 1024:.1f} MB JSON file")


if __name__ == '__main__':
    convert_airports()
