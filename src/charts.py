"""
Plotly chart builders for the Athlete OS Overview page.

Color usage:
- Recovery bands use the fixed WHOOP-style status colors (red/yellow/green).
- HRV and resting HR each get their own single-axis chart (never combined on
  one dual-axis chart) using distinct categorical hues.
- Workout activity types use the categorical palette in a fixed hue order.
"""

import plotly.graph_objects as go
import numpy as np
import pandas as pd

# Status colors (fixed, never reused for series identity)
COLOR_GOOD = "#0ca30c"
COLOR_WARNING = "#fab219"
COLOR_CRITICAL = "#d03b3b"

# Categorical palette (fixed order)
COLOR_BLUE = "#2a78d6"
COLOR_ORANGE = "#eb6834"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

MUTED = "#898781"
GRIDLINE = "#e1e0d9"
PRIMARY_INK = "#0b0b0b"

BASE_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=PRIMARY_INK, size=13),
    margin=dict(l=10, r=10, t=40, b=10),
    hovermode="x unified",
)


def recovery_trend_chart(phys: pd.DataFrame, sleeps: pd.DataFrame | None = None) -> go.Figure:
    d = phys.dropna(subset=["Recovery score %"]).sort_values("Cycle start time").copy()

    fig = go.Figure()

    if not d.empty:
        # Attach same-day main-sleep duration for richer hover context.
        if sleeps is not None and not sleeps.empty:
            main_sleep = sleeps[~sleeps["is_nap"]][["date", "Asleep duration (min)"]]
            main_sleep = main_sleep.groupby("date", as_index=False)["Asleep duration (min)"].mean()
            d = d.merge(main_sleep, on="date", how="left")
        else:
            d["Asleep duration (min)"] = pd.NA
        d["sleep_hours"] = d["Asleep duration (min)"] / 60

        y_max = 100
        # Background recovery bands (drawn first, low opacity, behind the line)
        fig.add_hrect(y0=0, y1=34, fillcolor=COLOR_CRITICAL, opacity=0.08, line_width=0)
        fig.add_hrect(y0=34, y1=67, fillcolor=COLOR_WARNING, opacity=0.08, line_width=0)
        fig.add_hrect(y0=67, y1=y_max, fillcolor=COLOR_GOOD, opacity=0.08, line_width=0)

        customdata = d[["Heart rate variability (ms)", "Resting heart rate (bpm)", "Day Strain", "sleep_hours"]].to_numpy()

        fig.add_trace(go.Scatter(
            x=d["Cycle start time"], y=d["Recovery score %"],
            mode="lines+markers",
            line=dict(color=PRIMARY_INK, width=2),
            marker=dict(size=5),
            name="Recovery %",
            customdata=customdata,
            hovertemplate=(
                "%{x|%b %d, %Y}<br>"
                "Recovery: %{y:.0f}%<br>"
                "HRV: %{customdata[0]:.0f} ms<br>"
                "Resting HR: %{customdata[1]:.0f} bpm<br>"
                "Day Strain: %{customdata[2]:.1f}<br>"
                "Sleep: %{customdata[3]:.1f} hrs"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(**BASE_LAYOUT, title="Recovery Score Over Time", height=340)
    fig.update_yaxes(range=[0, 100], title="Recovery %", gridcolor=GRIDLINE, zeroline=False)
    fig.update_xaxes(title=None, gridcolor=GRIDLINE)
    return fig


def _rolling_trend_chart(phys: pd.DataFrame, value_col: str, color: str, unit: str, title: str) -> go.Figure:
    d = phys.dropna(subset=[value_col]).sort_values("Cycle start time").copy()
    fig = go.Figure()

    if not d.empty:
        d["rolling_avg"] = d[value_col].rolling(window=7, min_periods=1).mean()

        fig.add_trace(go.Scatter(
            x=d["Cycle start time"], y=d[value_col],
            mode="lines", line=dict(color=color, width=1),
            opacity=0.25, name="Daily", showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=d["Cycle start time"], y=d["rolling_avg"],
            mode="lines", line=dict(color=color, width=2.5),
            name="7-day avg",
            hovertemplate=f"%{{x|%b %d, %Y}}<br>7-day avg: %{{y:.1f}} {unit}<extra></extra>",
        ))

    fig.update_layout(**BASE_LAYOUT, title=title, height=300, showlegend=False)
    fig.update_yaxes(title=unit, gridcolor=GRIDLINE, zeroline=False)
    fig.update_xaxes(title=None, gridcolor=GRIDLINE)
    return fig


def hrv_trend_chart(phys: pd.DataFrame) -> go.Figure:
    return _rolling_trend_chart(
        phys, "Heart rate variability (ms)", COLOR_BLUE, "ms",
        "HRV — ms (7-day avg)",
    )


def rhr_trend_chart(phys: pd.DataFrame) -> go.Figure:
    return _rolling_trend_chart(
        phys, "Resting heart rate (bpm)", COLOR_ORANGE, "bpm",
        "Resting Heart Rate — bpm (7-day avg)",
    )


def workout_breakdown_chart(workouts: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not workouts.empty:
        counts = workouts["Activity name"].value_counts().sort_values(ascending=True)

        fig.add_trace(go.Bar(
            x=counts.values, y=counts.index,
            orientation="h",
            marker=dict(color=COLOR_BLUE),
            text=counts.values,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x} workouts<extra></extra>",
        ))

    height = max(220, 40 * len(workouts["Activity name"].unique()) + 80) if not workouts.empty else 220
    fig.update_layout(**BASE_LAYOUT, title="Workout Frequency by Activity Type", height=height, showlegend=False)
    fig.update_xaxes(title="Workouts", gridcolor=GRIDLINE)
    fig.update_yaxes(title=None)
    return fig


def driver_scatter_chart(chart_df: pd.DataFrame, x_label: str, y_label: str, title: str, color: str) -> go.Figure:
    """
    Scatter + linear trend line for a Recovery Lab driver relationship.
    Expects chart_df with columns: date, x, y (already NaN-dropped upstream).
    """
    fig = go.Figure()
    d = chart_df.dropna(subset=["x", "y"])

    if not d.empty:
        fig.add_trace(go.Scatter(
            x=d["x"], y=d["y"],
            mode="markers",
            marker=dict(color=color, size=7, opacity=0.55, line=dict(width=0)),
            customdata=d["date"],
            hovertemplate=(
                "%{customdata|%b %d, %Y}<br>"
                f"{x_label}: " + "%{x:.1f}<br>"
                f"{y_label}: " + "%{y:.0f}%<extra></extra>"
            ),
        ))

        if len(d) >= 2 and d["x"].std(ddof=0) > 0:
            coeffs = np.polyfit(d["x"], d["y"], 1)
            xs = np.linspace(d["x"].min(), d["x"].max(), 50)
            ys = coeffs[0] * xs + coeffs[1]
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color=PRIMARY_INK, width=2, dash="dash"),
                name="Trend", hoverinfo="skip",
            ))

    fig.update_layout(**BASE_LAYOUT, title=title, height=320, showlegend=False)
    fig.update_xaxes(title=x_label, gridcolor=GRIDLINE)
    fig.update_yaxes(title=y_label, gridcolor=GRIDLINE)
    return fig


# Zone 0 (below Zone 1) -> Zone 5, low to high cardiovascular intensity
ZONE_COLORS = ["#e7eef7", "#bcd4ef", "#8bb7e3", "#4a8fd1", "#1f5fa8", "#0b2c52"]


def intensity_profile_chart(profile: pd.DataFrame, min_sample_size: int = 3) -> go.Figure:
    """
    Horizontal bar of average strain by activity, sorted high to low.
    Activities with fewer than `min_sample_size` sessions are drawn muted so
    a single-session outlier doesn't visually read the same as a reliable average.
    """
    fig = go.Figure()
    d = profile.dropna(subset=["avg_strain"]).sort_values("avg_strain", ascending=True)

    if not d.empty:
        colors = [COLOR_BLUE if s >= min_sample_size else MUTED for s in d["sessions"]]
        fig.add_trace(go.Bar(
            x=d["avg_strain"], y=d["activity"],
            orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1f}" for v in d["avg_strain"]],
            textposition="outside",
            cliponaxis=False,
            customdata=d["sessions"],
            hovertemplate="%{y}: %{x:.1f} avg strain<br>Sessions: %{customdata}<extra></extra>",
        ))

    height = max(240, 42 * len(d) + 80) if not d.empty else 240
    fig.update_layout(**BASE_LAYOUT, title="Average Strain by Activity (muted = fewer than 3 sessions)",
                       height=height, showlegend=False)
    fig.update_xaxes(title="Avg Strain", gridcolor=GRIDLINE)
    fig.update_yaxes(title=None)
    return fig


def hr_zone_stacked_chart(zone_df: pd.DataFrame) -> go.Figure:
    """Stacked horizontal bar of avg % workout time per HR zone, by activity."""
    fig = go.Figure()

    if not zone_df.empty:
        d = zone_df.sort_values("sessions", ascending=True)
        for z in range(6):
            col = f"Zone {z}"
            fig.add_trace(go.Bar(
                y=d["activity"], x=d[col],
                orientation="h",
                name=col,
                marker=dict(color=ZONE_COLORS[z]),
                customdata=d["sessions"],
                hovertemplate=f"%{{y}}<br>{col}: " + "%{x:.0f}% of workout time<br>Sessions: %{customdata}<extra></extra>",
            ))

    height = max(240, 42 * len(zone_df) + 100) if not zone_df.empty else 240
    fig.update_layout(
        **{**BASE_LAYOUT, "hovermode": "closest"},
        title="Heart Rate Zone Profile by Activity", height=height, barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title="% of workout time", range=[0, 100], gridcolor=GRIDLINE)
    fig.update_yaxes(title=None)
    return fig


def weekly_sessions_chart(weekly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not weekly.empty:
        fig.add_trace(go.Bar(
            x=weekly["week_start"], y=weekly["sessions"],
            marker=dict(color=COLOR_BLUE),
            hovertemplate="Week of %{x|%b %d, %Y}<br>Sessions: %{y}<extra></extra>",
        ))
    fig.update_layout(**BASE_LAYOUT, title="Workout Sessions per Week", height=260, showlegend=False)
    fig.update_xaxes(title=None, gridcolor=GRIDLINE)
    fig.update_yaxes(title="Sessions", gridcolor=GRIDLINE)
    return fig


def weekly_strain_chart(weekly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not weekly.empty:
        fig.add_trace(go.Scatter(
            x=weekly["week_start"], y=weekly["total_strain"],
            mode="lines+markers",
            line=dict(color=COLOR_ORANGE, width=2), marker=dict(size=5),
            hovertemplate="Week of %{x|%b %d, %Y}<br>Total strain: %{y:.1f}<extra></extra>",
        ))
    fig.update_layout(**BASE_LAYOUT, title="Total Workout Strain per Week", height=260, showlegend=False)
    fig.update_xaxes(title=None, gridcolor=GRIDLINE)
    fig.update_yaxes(title="Total Strain", gridcolor=GRIDLINE)
    return fig
