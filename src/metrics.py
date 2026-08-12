"""
KPI calculations and deterministic "Performance Snapshot" insights.

Every value here is computed from whatever DataFrame is passed in - nothing
is hard-coded - so results always reflect the currently selected date range.
"""

import datetime as dt

import pandas as pd


def safe_mean(series: pd.Series):
    """Mean that ignores NaNs and returns None (not NaN) when there's no data."""
    series = series.dropna()
    return float(series.mean()) if len(series) else None


def calendar_weeks(start_date: dt.date, end_date: dt.date) -> float:
    """Number of calendar weeks spanned by an inclusive date range."""
    span_days = (end_date - start_date).days + 1
    return span_days / 7


def compute_kpis(
    phys: pd.DataFrame, workouts: pd.DataFrame, sleeps: pd.DataFrame,
    start_date: dt.date, end_date: dt.date,
) -> dict:
    main_sleep = sleeps[~sleeps["is_nap"]]
    valid_duration_workouts = workouts[~workouts["duration_is_outlier"]]

    # Day Strain only finalizes when a cycle closes, so an open (in-progress)
    # cycle is excluded here rather than relying on it happening to be NaN.
    completed_cycles = phys[~phys["is_open_cycle"]]

    weeks = calendar_weeks(start_date, end_date)

    return {
        "days_tracked": phys["date"].nunique(),
        "total_workouts": len(workouts),
        "avg_recovery": safe_mean(phys["Recovery score %"]),
        "avg_hrv": safe_mean(phys["Heart rate variability (ms)"]),
        "avg_rhr": safe_mean(phys["Resting heart rate (bpm)"]),
        "avg_sleep_hours": (
            safe_mean(main_sleep["Asleep duration (min)"]) / 60
            if safe_mean(main_sleep["Asleep duration (min)"]) is not None else None
        ),
        "avg_day_strain": safe_mean(completed_cycles["Day Strain"]),
        "avg_workout_duration": safe_mean(valid_duration_workouts["Duration (min)"]),
        "sessions_per_week": (len(workouts) / weeks) if weeks > 0 else None,
        "_valid_duration_workouts": len(valid_duration_workouts),  # for reference/debug only
    }


def _trend_direction(df: pd.DataFrame, date_col: str, value_col: str, unit_label: str, thresh: float):
    """
    Compare the average of the first third vs. the last third of chronologically
    sorted, non-null values to describe a simple trend direction.
    """
    d = df[[date_col, value_col]].dropna().sort_values(date_col)
    if len(d) < 6:
        return None  # not enough points for a meaningful trend
    n = len(d)
    third = max(n // 3, 1)
    first_avg = d[value_col].iloc[:third].mean()
    last_avg = d[value_col].iloc[-third:].mean()
    delta = last_avg - first_avg

    if abs(delta) < thresh:
        direction = "held steady"
    elif delta > 0:
        direction = "trended up"
    else:
        direction = "trended down"

    return direction, delta


def generate_snapshot(
    phys: pd.DataFrame, workouts: pd.DataFrame, start_date: dt.date, end_date: dt.date,
) -> list[tuple[str, str]]:
    """Return up to 4 categorized, plain-language, data-driven observations
    as (category, text) pairs: Recovery, Fitness Trend, Training, Consistency.
    """
    observations = []

    # --- Recovery ---
    avg_recovery = safe_mean(phys["Recovery score %"])
    if avg_recovery is not None:
        if avg_recovery >= 67:
            band = "green"
        elif avg_recovery >= 34:
            band = "yellow"
        else:
            band = "red"
        observations.append((
            "Recovery",
            f"Average recovery was **{avg_recovery:.0f}%**, landing in the **{band}** range on average.",
        ))

    # --- Fitness Trend (HRV + resting HR direction) ---
    hrv_trend = _trend_direction(phys, "Cycle start time", "Heart rate variability (ms)", "ms", thresh=1.0)
    rhr_trend = _trend_direction(phys, "Cycle start time", "Resting heart rate (bpm)", "bpm", thresh=0.5)
    trend_parts = []
    if hrv_trend:
        direction, delta = hrv_trend
        trend_parts.append(f"HRV {direction} by **{abs(delta):.1f} ms**")
    if rhr_trend:
        direction, delta = rhr_trend
        trend_parts.append(f"resting heart rate {direction} by **{abs(delta):.1f} bpm**")
    if trend_parts:
        observations.append(("Fitness Trend", " and ".join(trend_parts).capitalize() + " across the selected period."))

    # --- Training (dominant activity) ---
    if len(workouts):
        counts = workouts["Activity name"].value_counts()
        top_activity, top_count = counts.idxmax(), counts.max()
        pct = 100 * top_count / len(workouts)
        observations.append((
            "Training",
            f"**{top_activity}** accounted for **{pct:.0f}%** of workouts "
            f"({top_count} of {len(workouts)} sessions).",
        ))

    # --- Consistency (sessions per week, calendar-week based) ---
    weeks = calendar_weeks(start_date, end_date)
    if len(workouts) and weeks > 0:
        per_week = len(workouts) / weeks
        observations.append((
            "Consistency",
            f"You averaged **{per_week:.1f} sessions per week** during this period.",
        ))

    return observations[:4]
