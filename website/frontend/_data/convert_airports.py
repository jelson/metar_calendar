#!/usr/bin/env python3
"""
Convert OurAirports CSV data to simplified JSON format for web autocomplete.

Filters airports to only include those with METAR data available from IEM.
Cross-references OurAirports data with IEM station list using lat/lon proximity (0.1 degrees).

Output fields: display, codes, name, location, query
- display: the airport's ident field (unique identifier for display/URLs)
- query: the IEM station identifier to use when querying IEM API (closest match by distance)
- codes: array of all unique codes (ident, icao_code, iata_code, local_code, gps_code)
- location: formatted string "Municipality, Region, Country Code" (parts omitted if not available)
"""

import airportsdata
import pandas as pd
from pathlib import Path
import requests
from io import StringIO

# URLs
OURAIRPORTS_URL = 'https://davidmegginson.github.io/ourairports-data/airports.csv'
IEM_STATIONS_URL = 'https://mesonet.agron.iastate.edu/sites/networks.php?network=_ALL_&format=csv&nohtml=on'

# Output paths
OUTPUT_JSON = Path(__file__).parent / '../assets/data/airports_v3.json'
OUTPUT_METADATA = Path(__file__).parent / '../../backend/data/airport_metadata.parquet'


def fetch_iem_stations():
    """Download list of all IEM weather stations with lat/lon."""
    print(f"Fetching IEM station list from {IEM_STATIONS_URL}...")
    response = requests.get(IEM_STATIONS_URL, timeout=30)
    response.raise_for_status()

    # Parse CSV from response
    iem_df = pd.read_csv(StringIO(response.text))

    print(f"Found {len(iem_df)} IEM stations")

    # Keep station ID, lat, lon and normalize to uppercase
    iem_df = iem_df[['stid', 'lat', 'lon']].copy()
    iem_df['stid'] = iem_df['stid'].str.strip().str.upper()

    # Check for duplicates before setting index
    if iem_df['stid'].duplicated().any():
        duplicates = iem_df[iem_df['stid'].duplicated(keep=False)]['stid'].unique()
        print(f"WARNING: Found {len(duplicates)} duplicate station IDs: {list(duplicates)[:10]}")
        # Keep first occurrence of each duplicate
        iem_df = iem_df.drop_duplicates(subset='stid', keep='first')
        print(f"Kept first occurrence, reduced to {len(iem_df)} unique stations")

    # Set stid as index for fast lookups
    iem_df = iem_df.set_index('stid')

    print(f"Extracted {len(iem_df)} IEM stations with coordinates (indexed by stid)")
    return iem_df


def convert_airports():
    """Load CSV, cross-reference with IEM stations, and export to JSON."""

    # Fetch IEM stations first
    iem_stations = fetch_iem_stations()

    # Fetch OurAirports CSV
    print(f"\nFetching OurAirports data from {OURAIRPORTS_URL}...")
    response = requests.get(OURAIRPORTS_URL, timeout=30)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text), usecols=[
        'ident', 'icao_code', 'iata_code', 'local_code', 'gps_code',
        'name', 'municipality', 'iso_region', 'iso_country', 'latitude_deg', 'longitude_deg'
    ])

    print(f"Total airports in OurAirports database: {len(df)}")

    # Strip whitespace
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # Replace empty strings with None
    df = df.replace('', None)

    # Cross-reference with IEM stations using lat/lon proximity (within 0.1 degrees)
    print("Matching airports to IEM stations with location check...")

    df['ident_upper'] = df['ident'].str.upper()
    df['icao_upper'] = df['icao_code'].str.upper()
    df['iata_upper'] = df['iata_code'].str.upper()
    df['local_upper'] = df['local_code'].str.upper()
    df['gps_upper'] = df['gps_code'].str.upper()

    # Step 1: Check which codes exist in IEM index
    df['ident_in_iem'] = df['ident_upper'].isin(iem_stations.index)
    df['icao_in_iem'] = df['icao_upper'].isin(iem_stations.index)
    df['iata_in_iem'] = df['iata_upper'].isin(iem_stations.index)
    df['local_in_iem'] = df['local_upper'].isin(iem_stations.index)
    df['gps_in_iem'] = df['gps_upper'].isin(iem_stations.index)

    # Step 2: For airports with at least one code match, find closest match within 0.1 degrees
    has_code_match = df['ident_in_iem'] | df['icao_in_iem'] | df['iata_in_iem'] | df['local_in_iem'] | df['gps_in_iem']
    df_matches = df[has_code_match].copy()

    def find_closest_match(row):
        """Find the closest IEM station match within 0.1 degrees, returns the IEM code or None"""
        lat = row['latitude_deg']
        lon = row['longitude_deg']
        if pd.isna(lat) or pd.isna(lon):
            return None

        # Priority order for checking codes (only need the uppercase IEM version)
        codes = [
            (row['ident_upper'], row['ident_in_iem']),
            (row['icao_upper'], row['icao_in_iem']),
            (row['iata_upper'], row['iata_in_iem']),
            (row['local_upper'], row['local_in_iem']),
            (row['gps_upper'], row['gps_in_iem'])
        ]

        best_match = None
        best_distance = float('inf')

        for code_upper, matched in codes:
            if matched and pd.notna(code_upper):
                station = iem_stations.loc[code_upper]
                # Calculate distance (simple Euclidean in degrees)
                lat_diff = abs(station['lat'] - lat)
                lon_diff = abs(station['lon'] - lon)
                distance = (lat_diff ** 2 + lon_diff ** 2) ** 0.5

                # Check if within 0.1 degrees threshold in both dimensions
                if lat_diff < 0.1 and lon_diff < 0.1:
                    if distance < best_distance:
                        best_distance = distance
                        best_match = code_upper  # Use the IEM code

        return best_match

    # Find the best matching code for each airport
    df.loc[has_code_match, 'query'] = df_matches.apply(find_closest_match, axis=1)

    # Filter: keep only airports that have a valid match
    df = df[df['query'].notna()]

    # Create 'codes' array with all unique codes for each airport
    def create_codes_array(row):
        codes = []
        for col in ['ident', 'icao_code', 'iata_code', 'local_code', 'gps_code']:
            if pd.notna(row[col]) and row[col]:
                code = row[col].strip().upper()
                if code and code not in codes:
                    codes.append(code)
        # Sort by length (longest first), then alphabetically
        codes.sort(key=lambda x: (-len(x), x))
        return codes

    df['codes'] = df.apply(create_codes_array, axis=1)

    # Add 'display' field using ident (uppercase)
    df['display'] = df['ident'].str.strip().str.upper()

    # Create 'location' field: "Municipality, Region, Country Code"
    def create_location(row):
        parts = []

        # Add municipality if available
        if pd.notna(row['municipality']) and row['municipality']:
            parts.append(row['municipality'])

        # Parse iso_region to get region (after the dash)
        if pd.notna(row['iso_region']) and row['iso_region']:
            region_parts = row['iso_region'].split('-', 1)
            if len(region_parts) == 2 and region_parts[1]:
                parts.append(region_parts[1])

        # Add country code
        if pd.notna(row['iso_country']) and row['iso_country']:
            parts.append(row['iso_country'])

        return ', '.join(parts) if parts else ''

    df['location'] = df.apply(create_location, axis=1)

    # Look up timezone for each airport using airportsdata (keyed by ICAO)
    tz_db = airportsdata.load()
    df['tz'] = df['display'].map(lambda code: tz_db.get(code, {}).get('tz'))
    tz_found = df['tz'].notna().sum()
    print(f"Timezone lookup: {tz_found}/{len(df)} airports matched in airportsdata")

    # Generate backend metadata parquet (airport_code -> tz, extensible later)
    # Done before column trimming so 'tz' is still available
    metadata = df[['query', 'tz']].copy()
    metadata = metadata.rename(columns={'query': 'airport_code'})
    metadata = metadata.set_index('airport_code')
    OUTPUT_METADATA.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_parquet(OUTPUT_METADATA)
    print(f"Generated {OUTPUT_METADATA} ({len(metadata)} airports, {OUTPUT_METADATA.stat().st_size / 1024:.0f} KB)")

    # Keep only the columns we need for frontend JSON output
    df = df[['display', 'codes', 'name', 'location', 'query']]

    print(f"Airports with IEM METAR data: {len(df)}")

    # Check for duplicate display codes - this should never happen
    if df['display'].duplicated().any():
        duplicates = df[df['display'].duplicated(keep=False)][['display', 'name', 'location']]
        print("\nERROR: Multiple airports have the same ident!")
        print(duplicates.to_string())
        raise ValueError(f"Found {df['display'].duplicated().sum()} duplicate display codes - data integrity failure")

    # Check for duplicate query codes - this should never happen
    if df['query'].duplicated().any():
        duplicates = df[df['query'].duplicated(keep=False)][['query', 'name', 'location']]
        print("\nERROR: Multiple airports matched to the same IEM station!")
        print(duplicates.to_string())
        raise ValueError(f"Found {df['query'].duplicated().sum()} duplicate query codes - data integrity failure")

    # Sort by query code
    df = df.sort_values('query')

    # Write JSON
    print(f"\nWriting {len(df)} airports to {OUTPUT_JSON}...")
    df.to_json(OUTPUT_JSON, orient='records', force_ascii=False, indent=2)

    print(f"Done! Generated {OUTPUT_JSON.stat().st_size / 1024 / 1024:.1f} MB JSON file")


if __name__ == '__main__':
    convert_airports()
