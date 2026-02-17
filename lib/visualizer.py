import calendar
import math
import pandas as pd
import plotly.graph_objects as go


class METARVisualizer:
    COLORS = {
        'VFR': 'green',
        'MVFR': 'blue',
        'IFR': 'red',
        'LIFR': 'magenta'
    }

    @staticmethod
    def _format_local_hour(utc_hour, offset_hours):
        """Convert a UTC hour + offset to compact AM/PM format.

        e.g., _format_local_hour(0, -7) => "5p"
              _format_local_hour(13, 5.5) => "6:30p"
        """
        local_hour = (utc_hour + offset_hours) % 24
        if local_hour < 0:
            local_hour += 24

        hour_int = math.floor(local_hour)
        minutes = round((local_hour - hour_int) * 60)

        period = 'p' if hour_int >= 12 else 'a'
        if hour_int == 0:
            display_hour = 12
        elif hour_int > 12:
            display_hour = hour_int - 12
        else:
            display_hour = hour_int

        if minutes > 0:
            return f"{display_hour}:{minutes:02d}{period}"
        return f"{display_hour}{period}"

    @staticmethod
    def generate_png(hourly_df: pd.DataFrame, utc_offsets=None, daylight_utc=None) -> bytes:
        airport = hourly_df.attrs.get('airport', 'Unknown')
        month = hourly_df.attrs.get('month')
        month_name = calendar.month_name[month] if month else 'Unknown'

        hours = list(range(24))

        # Build stacked bar traces (VFR on bottom)
        fig = go.Figure()
        for condition in ['VFR', 'MVFR', 'IFR', 'LIFR']:
            values = []
            for hour in hours:
                if hour in hourly_df.index:
                    values.append(hourly_df.loc[hour, condition])
                else:
                    values.append(0)
            fig.add_trace(go.Bar(
                x=hours,
                y=values,
                name=condition,
                marker_color=METARVisualizer.COLORS[condition],
            ))

        has_timezone = utc_offsets is not None and len(utc_offsets) > 0

        # Bottom margin: base for tick labels, plus extra per timezone row
        extra_row_height = 16
        base_bottom = 25 if has_timezone else 70
        bottom_margin = base_bottom + (len(utc_offsets) * extra_row_height if has_timezone else 0)

        layout = dict(
            barmode='stack',
            width=800,
            height=400,
            title=f'{airport}, {month_name}',
            xaxis=dict(
                title='' if has_timezone else dict(text='UTC hour', standoff=10),
                dtick=1,
                range=[-0.5, 23.5],
            ),
            yaxis=dict(
                title=dict(text='Fraction of Days', standoff=10),
                tickformat='.0%',
            ),
            legend=dict(
                traceorder='reversed',
                orientation='h',
                x=0.5,
                xanchor='center',
                y=1.02,
                yanchor='bottom',
            ),
            margin=dict(l=70, r=10, t=40, b=bottom_margin),
        )

        # Multi-line x-axis tick labels with local time rows
        if has_timezone:
            tickvals = []
            ticktext = []

            for hour in range(24):
                tickvals.append(hour)
                lines = [str(hour)]
                for offset in utc_offsets:
                    lines.append(METARVisualizer._format_local_hour(
                        hour, offset['utc_offset_hours']))
                ticktext.append('<br>'.join(lines))

            # Label column on the left
            label_lines = ['<b>UTC</b>']
            for offset in utc_offsets:
                label_lines.append(f"<b>{offset['abbr']}</b>")
            tickvals.insert(0, -1)
            ticktext.insert(0, '<br>'.join(label_lines))

            layout['xaxis']['tickvals'] = tickvals
            layout['xaxis']['ticktext'] = ticktext
            layout['xaxis']['tickfont'] = dict(size=10)
            layout['xaxis']['tickangle'] = 0
            layout['xaxis']['range'] = [-1.5, 23.5]

        fig.update_layout(**layout)

        # Add daylight background shapes
        if daylight_utc is not None:
            sunrise = daylight_utc['sunrise']
            sunset = daylight_utc['sunset']
            x_min = -0.5
            x_max = 23.5
            shape_style = dict(
                type='rect',
                xref='x',
                yref='paper',
                y0=0,
                y1=1,
                fillcolor='rgba(255, 255, 0, 0.4)',
                line=dict(width=0),
                layer='below',
            )

            if sunrise < sunset:
                fig.add_shape(**shape_style, x0=sunrise, x1=sunset)
            else:
                # Daylight wraps around midnight UTC
                fig.add_shape(**shape_style, x0=x_min, x1=sunset)
                fig.add_shape(**shape_style, x0=sunrise, x1=x_max)

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
