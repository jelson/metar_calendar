import calendar
import pandas as pd
import plotly.express as px


class METARVisualizer:
    COLORS = {
        'VFR': 'green',
        'MVFR': 'blue',
        'IFR': 'red',
        'LIFR': 'magenta'
    }

    @staticmethod
    def generate_png(hourly_df: pd.DataFrame) -> bytes:
        airport = hourly_df.attrs.get('airport', 'Unknown')
        month = hourly_df.attrs.get('month')
        month_name = calendar.month_name[month] if month else 'Unknown'

        fig = px.bar(
            hourly_df,
            width=800,
            height=400,
            color_discrete_map=METARVisualizer.COLORS,
        )
        fig.update_layout(
            xaxis={'dtick': 1},
            yaxis_title='Fraction of Days',
            legend={'traceorder': 'reversed'},
            title=f'{airport}, {month_name}',
        )
        return fig.to_image(format='png')

    @staticmethod
    def format_table(hourly_df: pd.DataFrame) -> str:
        airport = hourly_df.attrs.get('airport', 'Unknown')
        month = hourly_df.attrs.get('month')
        month_name = calendar.month_name[month] if month else 'Unknown'

        lines = []
        lines.append(f"\n{airport}, {month_name}")
        lines.append("=" * 80)
        lines.append(f"{'Hour':>4} {'VFR':>6} {'MVFR':>6} {'IFR':>6} {'LIFR':>6}")
        lines.append("-" * 80)

        for hour in range(24):
            vfr = hourly_df.loc[hour, 'VFR'] if hour in hourly_df.index else 0
            mvfr = hourly_df.loc[hour, 'MVFR'] if hour in hourly_df.index else 0
            ifr = hourly_df.loc[hour, 'IFR'] if hour in hourly_df.index else 0
            lifr = hourly_df.loc[hour, 'LIFR'] if hour in hourly_df.index else 0
            lines.append(f"{hour:4d} {vfr:6.2%} {mvfr:6.2%} {ifr:6.2%} {lifr:6.2%}")

        lines.append("=" * 80)
        return '\n'.join(lines)

    @staticmethod
    def to_dict(hourly_df: pd.DataFrame) -> dict:
        airport = hourly_df.attrs.get('airport')
        month = hourly_df.attrs.get('month')
        return {
            'airport': airport,
            'month': month,
            'hourly_stats': {
                int(hour): {
                    'VFR': float(row['VFR']),
                    'MVFR': float(row['MVFR']),
                    'IFR': float(row['IFR']),
                    'LIFR': float(row['LIFR']),
                }
                for hour, row in hourly_df.iterrows()
            }
        }
