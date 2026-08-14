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


# WHOOP's own recovery-score banding (used for both the Athlete Intelligence
# "Recovery" insight and the Overview KPI card's contextual label).
RECOVERY_GREEN_THRESHOLD = 67
RECOVERY_YELLOW_THRESHOLD = 34


def recovery_band_label(avg_recovery) -> str | None:
    """WHOOP recovery band ("GREEN RANGE" / "YELLOW RANGE" / "RED RANGE") for a recovery %, or None if unavailable."""
    if avg_recovery is None:
        return None
    if avg_recovery >= RECOVERY_GREEN_THRESHOLD:
        return "GREEN RANGE"
    elif avg_recovery >= RECOVERY_YELLOW_THRESHOLD:
        return "YELLOW RANGE"
    else:
        return "RED RANGE"


def trend_direction(df: pd.DataFrame, date_col: str, value_col: str, unit_label: str, thresh: float):
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


def get_performance_trend_label(phys: pd.DataFrame) -> str:
    """
    Deterministic Improving / Declining / Mixed / Stable / "Not enough data"
    label derived from the same HRV and resting-HR trend directions already
    used in the "Fitness Trend" Athlete Intelligence insight below. This is
    a categorical rollup of existing trend directions, not a new metric or
    a fabricated score.
    """
    hrv_trend = trend_direction(phys, "Cycle start time", "Heart rate variability (ms)", "ms", thresh=1.0)
    rhr_trend = trend_direction(phys, "Cycle start time", "Resting heart rate (bpm)", "bpm", thresh=0.5)

    if hrv_trend is None and rhr_trend is None:
        return "Not enough data"

    hrv_dir = hrv_trend[0] if hrv_trend else "held steady"
    rhr_dir = rhr_trend[0] if rhr_trend else "held steady"

    # Favorable: HRV trending up and/or resting HR trending down.
    favorable = hrv_dir == "trended up" or rhr_dir == "trended down"
    unfavorable = hrv_dir == "trended down" or rhr_dir == "trended up"

    if favorable and not unfavorable:
        return "Improving"
    if unfavorable and not favorable:
        return "Declining"
    if not favorable and not unfavorable:
        return "Stable"
    return "Mixed"


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
        band = recovery_band_label(avg_recovery).split(" ")[0].lower()  # "GREEN RANGE" -> "green"
        observations.append((
            "Recovery",
            f"Average recovery was **{avg_recovery:.0f}%**, landing in the **{band}** range on average.",
        ))

    # --- Fitness Trend (HRV + resting HR direction) ---
    hrv_trend = trend_direction(phys, "Cycle start time", "Heart rate variability (ms)", "ms", thresh=1.0)
    rhr_trend = trend_direction(phys, "Cycle start time", "Resting heart rate (bpm)", "bpm", thresh=0.5)
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
