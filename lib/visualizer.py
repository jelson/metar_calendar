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
        airport = hourly_df.attrs['airport']
        month = hourly_df.attrs['month']
        month_name = calendar.month_name[month]

        lines = []
        lines.append(f"\n{airport}, {month_name}")
        lines.append(f"{'Hour':>4} {'VFR':>5} {'MVFR':>5} {'IFR':>5} {'LIFR':>5}")
        lines.append("-" * 30)

        for hour in range(24):
            if hour in hourly_df.index:
                vfr = hourly_df.loc[hour, 'VFR']
                mvfr = hourly_df.loc[hour, 'MVFR']
                ifr = hourly_df.loc[hour, 'IFR']
                lifr = hourly_df.loc[hour, 'LIFR']
                lines.append(f"{hour:4d} {vfr:5.0%} {mvfr:5.0%} {ifr:5.0%} {lifr:5.0%}")
            else:
                lines.append(f"{hour:4d} {'--':>5} {'--':>5} {'--':>5} {'--':>5}")
        return '\n'.join(lines)
