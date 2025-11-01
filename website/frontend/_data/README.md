# Airport Data

## Source

Airport data comes from [OurAirports](https://ourairports.com/), at https://davidmegginson.github.io/ourairports-data/airports.csv

`convert_airports.py` converts the CSV into JSON, which is loaded by the website for use in
the search bar's autocomplete. Airports are filtered out if they don't have an ICAO code, IATA code or name. They are deduplicated by ICAO code.

The only four fields extracted are the ones used by autocomplete:
   - `icao` - ICAO 4-letter code (e.g., "KSEA")
   - `iata` - IATA 3-letter code (e.g., "SEA") or null
   - `name` - Airport name (e.g., "Seattle–Tacoma International Airport")
   - `city` - Municipality/city name (e.g., "Seattle")
   - `country` - ISO country code (e.g., "US")
