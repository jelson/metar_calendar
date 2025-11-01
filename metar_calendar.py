#!/usr/bin/env python3

from dateutil.relativedelta import relativedelta
from enum import IntEnum
import appdirs
import argparse
import calendar
import datetime
import io
import os
import pandas as pd
import plotly.express as px
import pytz
import re
import requests
import sys
import time

def say(s):
    d = datetime.datetime.now().replace(microsecond=0)
    sys.stderr.write(f'{d}: {str(s)}\n')
    sys.stderr.flush()

class OgimetFetcher:
    # Get metar+speci data for a single year/month. Returns a
    # dataframe with columns 'date' (datetime) and 'metar_txt'
    # (string).
    def _fetch_month(self, year, month):
        say(f'Fetching c={self.code} y={year}, m={month}')
        resp = requests.get('https://www.ogimet.com/display_metars2.php', params={
            'lang': 'en',
            'lugar': self.code,
            'tipo': 'ALL',
            'fmt': 'txt',
            'nil': 'NO',

            # start
            'ano': year,
            'mes': month,
            'day': 1,
            'hora': 0,

            # end
            'anof': year,
            'mesf': month,
            'dayf': 31,
            'horaf': 23,
            'minf': 59,
        })

        # throw an exception if not a good response
        resp.raise_for_status()

        dates = []
        metars = []
        for line in resp.iter_lines():
            line = line.decode('utf8', errors='ignore')
            mo = re.search(r'^(\d\d\d\d)(\d\d)(\d\d)(\d\d)(\d\d) (METAR|SPECI)(.*)(=)$', line)
            if mo:
                dates.append(datetime.datetime(
                    year=int(mo.group(1)),
                    month=int(mo.group(2)),
                    day=int(mo.group(3)),
                    hour=int(mo.group(4)),
                    minute=int(mo.group(5)),
                    tzinfo=datetime.timezone.utc,
                ))
                metars.append(''.join(mo.groups()[6:]))

        df = pd.DataFrame({'date': dates, 'metar_text': metars})
        return df

    def _fetch(self):
        fetch_date = datetime.datetime.today()
        month_dfs = []
        for months_ago in range(13):
            month_dfs.append(self._fetch_month(fetch_date.year, fetch_date.month))
            fetch_date -= relativedelta(months=1)
            time.sleep(5)
        df = pd.concat(month_dfs)
        df = df.sort_values('date').reset_index()

class MetarArchive:
    CACHE_DIR = appdirs.user_cache_dir("metar_calendar")
    NUM_MONTHS = 24

    def __init__(self, airport_code):
        self.code = airport_code.upper().strip()

    def _cache_filename(self):
        fn = os.path.join(self.CACHE_DIR, self.code + ".parquet")
        dirn = os.path.dirname(fn)
        if not os.path.exists(dirn):
            os.makedirs(dirn)
        return fn

    def _fetch(self):
        end_date = datetime.datetime.utcnow()
        start_date = end_date - relativedelta(months=self.NUM_MONTHS)
        say(f'Fetching data for {self.code}')

        resp = requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py', params={
            'station': self.code,
            'data': 'all',
            'year1': start_date.year,
            'month1': start_date.month,
            'day1': 1,
            'year2': end_date.year,
            'month2': end_date.month,
            'day2': end_date.day,
            'tz': 'Etc/UTC',
            'format': 'onlycomma',
            'latlon': 'no',
            'elev': 'no',
            'missing': 'empty',
            'trace': 'T',
            'direct': 'no',
            'report_type': [3, 4],
        })

        # throw an exception if not a good response
        resp.raise_for_status()

        df = pd.read_csv(io.StringIO(resp.content.decode('utf8', errors='ignore')))
        df = df.rename({'valid': 'date'}, axis=1)
        df = df.sort_values('date').reset_index(drop=True)
        df['date'] = df['date'].apply(
            lambda d: datetime.datetime.strptime(d, "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC))
        return df

    def get_dataframe(self, force=False):
        if force or not os.path.exists(self._cache_filename()):
            df = self._fetch()
            df.to_parquet(self._cache_filename())

        return pd.read_parquet(self._cache_filename())

class FlightCondition(IntEnum):
    LIFR = 1
    IFR  = 2
    MVFR = 3
    VFR  = 4
    
def annotate_with_flightrule(df):
    def classify(obs):
        # Get lowest ceiling (broken or overcast layer)
        ceil = 100000

        for i in range(4):
            condition = obs.get(f'skyc{i+1}', None)
            height = obs.get(f'skyl{i+1}', None)
            if pd.isna(condition) or pd.isna(height):
                continue
            if not condition in ('BKN', 'OVC', 'VV'):
                continue
            if not ceil or height < ceil:
                ceil = height

        # Get visibility
        vis = obs['vsby']

        if ceil >= 3000 and vis >= 5:
            return FlightCondition.VFR
        if ceil >= 1000 and vis >= 3:
            return FlightCondition.MVFR
        if ceil >= 500 and vis >= 1:
            return FlightCondition.IFR
        return FlightCondition.LIFR

    # Classify each observation according to flight rule
    df['Sky Condition'] = df.apply(classify, axis=1)

def get_hourly_for_month(df, month):
    # Find just observations from the requested month
    df = df.loc[df['date'].dt.month == month]
    #print(df[['date', 'vsby', 'skyl1', 'skyc1', 'skyl2', 'skyc2', 'Sky Condition']])

    # Move all timestamps forward by 10 minutes, so that an observation at 17:53
    # counts as the weather for 18:00.
    #
    # In cases where we have more than one observation in a single
    # hour, find the worst flight rule that occurred during that hour
    grouping = (df['date'] + datetime.timedelta(minutes=0)).dt.floor('1h')
    worst_every_hour = df.groupby(grouping)['Sky Condition'].agg('min')

    # For every one of the 24 hours, count how many times a flight
    # condition occurred during that hour
    hourly = worst_every_hour.groupby(worst_every_hour.index.hour).value_counts().unstack().fillna(0)

    # Convert raw counts into percentages
    hourly = hourly.apply(lambda row: row / row.sum(), axis=1)

    # Rename the axes
    hourly.index = hourly.index.rename('UTC hour')
    hourly = hourly.rename({r.value: r.name for r in FlightCondition}, axis=1)

    # Reverse column order so VFR is on bottom (plotly stacks left to right)
    hourly = hourly[['VFR', 'MVFR', 'IFR', 'LIFR']]

    return hourly

def print_hourly_table(hourly, airport, monthname):
    """Print the hourly data as a text table"""
    print(f"\n{airport}, {monthname}")
    print("=" * 80)
    print(f"{'Hour':>4} {'VFR':>6} {'MVFR':>6} {'IFR':>6} {'LIFR':>6}")
    print("-" * 80)
    for hour in range(24):
        vfr = hourly.loc[hour, 'VFR'] if hour in hourly.index else 0
        mvfr = hourly.loc[hour, 'MVFR'] if hour in hourly.index else 0
        ifr = hourly.loc[hour, 'IFR'] if hour in hourly.index else 0
        lifr = hourly.loc[hour, 'LIFR'] if hour in hourly.index else 0
        print(f"{hour:4d} {vfr:6.2%} {mvfr:6.2%} {ifr:6.2%} {lifr:6.2%}")
    print("=" * 80)

def draw_graph(args, hourly):
    airport = args.airport.upper()
    monthname = calendar.month_name[args.month]
    say(f'Plotting {airport} for {monthname}')

    # Print text table if requested
    if args.print_table:
        print_hourly_table(hourly, airport, monthname)

    fig = px.bar(
        hourly,
        width=800,
        height=400,
        color_discrete_map={'VFR': 'green', 'MVFR': 'blue', 'IFR': 'red', 'LIFR': 'magenta'},
    )
    fig.update_layout(
        xaxis={'dtick': 1},
        yaxis_title='Fraction of Days',
        legend={'traceorder': 'reversed'},
        title=f'{airport}, {monthname}',
    )
    if not args.output:
        args.output = f'{airport}-{args.month:02}.png'
    fig.write_image(args.output)

def get_args():
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
    return parser.parse_args()
    
def main():
    args = get_args()
    ma = MetarArchive(args.airport)
    df = ma.get_dataframe()
    annotate_with_flightrule(df)
    hourly = get_hourly_for_month(df, args.month)
    draw_graph(args, hourly)

if __name__ == "__main__":
    main()
