"""
Training Intelligence analysis: compares training load, intensity, duration,
and cardiovascular demand across workout activity types.

Descriptive statistics only - no prediction, no ML. Every function operates
on whatever date/activity-filtered DataFrame is passed in.
"""

import pandas as pd

from src.metrics import safe_mean

MIN_SAMPLE_SIZE = 3  # below this, a stat is flagged as a small sample rather than a definitive winner

ZONE_PCT_COLS = ["HR Zone 1 %", "HR Zone 2 %", "HR Zone 3 %", "HR Zone 4 %", "HR Zone 5 %"]
MIN_ZONE_SESSIONS = 3  # activities need at least this many valid zone records to be charted


def compute_activity_profile(workouts: pd.DataFrame) -> pd.DataFrame:
    """
    Per-activity summary: sessions, avg strain, avg duration (outlier-excluded),
    avg calories, avg HR, avg max HR. One row per Activity name, sorted by
    session count descending.
    """
    cols = ["activity", "sessions", "avg_strain", "avg_duration", "avg_calories", "avg_hr", "avg_max_hr"]
    if workouts.empty:
        return pd.DataFrame(columns=cols)

    valid_duration = workouts[~workouts["duration_is_outlier"]]

    rows = []
    for activity, grp in workouts.groupby("Activity name"):
        dur_grp = valid_duration[valid_duration["Activity name"] == activity]
        rows.append({
            "activity": activity,
            "sessions": len(grp),
            "avg_strain": safe_mean(grp["Activity Strain"]),
            "avg_duration": safe_mean(dur_grp["Duration (min)"]),
            "avg_calories": safe_mean(grp["Energy burned (cal)"]),
            "avg_hr": safe_mean(grp["Average HR (bpm)"]),
            "avg_max_hr": safe_mean(grp["Max HR (bpm)"]),
        })

    return pd.DataFrame(rows, columns=cols).sort_values("sessions", ascending=False).reset_index(drop=True)


def compute_training_kpis(workouts: pd.DataFrame) -> dict:
    """Aggregate KPIs over whatever workout subset is passed (date + activity filtered)."""
    valid_duration = workouts[~workouts["duration_is_outlier"]]
    return {
        "total_sessions": len(workouts),
        "avg_strain": safe_mean(workouts["Activity Strain"]),
        "avg_duration": safe_mean(valid_duration["Duration (min)"]),
        "avg_calories": safe_mean(workouts["Energy burned (cal)"]),
        "avg_hr": safe_mean(workouts["Average HR (bpm)"]),
        "avg_max_hr": safe_mean(workouts["Max HR (bpm)"]),
    }


def compute_hr_zone_profile(workouts: pd.DataFrame, min_sessions: int = MIN_ZONE_SESSIONS) -> pd.DataFrame:
    """
    Average % of workout time spent in each HR zone, by activity.

    WHOOP's export only provides Zone 1-5 percentages; Zone 0 (below Zone 1,
    i.e. low-intensity/warm-up time) is derived as the remainder:
    100 - sum(Zone 1..5), clipped at 0 to absorb rounding.

    Only activities with at least `min_sessions` valid zone records are
    included, so a single unusual session can't misrepresent an activity's
    typical intensity profile.
    """
    zone_cols = ["Zone 0", "Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"]
    cols = ["activity", "sessions"] + zone_cols
    d = workouts.dropna(subset=ZONE_PCT_COLS).copy()
    if d.empty:
        return pd.DataFrame(columns=cols)

    d["Zone 0"] = (100 - d[ZONE_PCT_COLS].sum(axis=1)).clip(lower=0)
    for i, col in enumerate(ZONE_PCT_COLS, start=1):
        d[f"Zone {i}"] = d[col]

    rows = []
    for activity, grp in d.groupby("Activity name"):
        if len(grp) < min_sessions:
            continue
        row = {"activity": activity, "sessions": len(grp)}
        for z in zone_cols:
            row[z] = grp[z].mean()
        rows.append(row)

    return pd.DataFrame(rows, columns=cols).sort_values("sessions", ascending=False).reset_index(drop=True)


def compute_weekly_training_volume(workouts: pd.DataFrame) -> pd.DataFrame:
    """Weekly (Mon-start) session counts and summed strain."""
    cols = ["week_start", "sessions", "total_strain"]
    if workouts.empty:
        return pd.DataFrame(columns=cols)

    d = workouts.copy()
    dates = pd.to_datetime(d["date"])
    d["week_start"] = dates - pd.to_timedelta(dates.dt.weekday, unit="D")

    weekly = d.groupby("week_start").agg(
        sessions=("Activity name", "count"),
        total_strain=("Activity Strain", "sum"),
    ).reset_index()

    return weekly.sort_values("week_start")


def filter_profile(profile: pd.DataFrame, activities: list[str]) -> pd.DataFrame:
    """Subset an activity profile to a specific list, preserving the given order, skipping absent ones."""
    present = [a for a in activities if a in profile["activity"].values]
    if not present:
        return profile.iloc[0:0]
    return profile.set_index("activity").loc[present].reset_index()


def _small_sample_note(row: pd.Series) -> str:
    return f" (small sample, n={int(row['sessions'])})" if row["sessions"] < MIN_SAMPLE_SIZE else ""


def generate_comparison_insights(profile: pd.DataFrame, max_insights: int = 3) -> list[str]:
    """
    2-3 deterministic sentences comparing the activities present in `profile`
    (already filtered to the activities of interest, e.g. Cricket vs Gym).
    """
    insights = []

    valid_strain = profile.dropna(subset=["avg_strain"])
    if len(valid_strain) >= 2:
        hi = valid_strain.loc[valid_strain["avg_strain"].idxmax()]
        lo = valid_strain.loc[valid_strain["avg_strain"].idxmin()]
        if lo["avg_strain"] > 0 and hi["activity"] != lo["activity"]:
            pct = (hi["avg_strain"] - lo["avg_strain"]) / lo["avg_strain"] * 100
            insights.append(
                f"**{hi['activity']}** produced {pct:.0f}% higher average strain than "
                f"**{lo['activity']}**{_small_sample_note(hi)}{_small_sample_note(lo)}."
            )

    valid_duration = profile.dropna(subset=["avg_duration"])
    if len(valid_duration) >= 2:
        hi = valid_duration.loc[valid_duration["avg_duration"].idxmax()]
        lo = valid_duration.loc[valid_duration["avg_duration"].idxmin()]
        if hi["activity"] != lo["activity"]:
            diff = hi["avg_duration"] - lo["avg_duration"]
            insights.append(
                f"**{hi['activity']}** sessions lasted {diff:.0f} minutes longer on average than "
                f"**{lo['activity']}**{_small_sample_note(hi)}{_small_sample_note(lo)}."
            )

    valid_hr = profile.dropna(subset=["avg_hr"])
    if len(valid_hr) >= 2:
        lo = valid_hr.loc[valid_hr["avg_hr"].idxmin()]
        insights.append(
            f"**{lo['activity']}** showed the lowest average cardiovascular load among the compared "
            f"activities ({lo['avg_hr']:.0f} bpm avg HR){_small_sample_note(lo)}."
        )

    return insights[:max_insights]


def training_summary(profile: pd.DataFrame) -> dict:
    """
    Headline stats across the full (date-filtered) activity profile:
    most frequent activity, highest avg strain, longest avg duration,
    highest avg calories, highest avg HR. Each entry carries its session
    count so the UI can flag small samples.
    """
    if profile.empty:
        return {}

    def best(col: str):
        valid = profile.dropna(subset=[col])
        if valid.empty:
            return None
        row = valid.loc[valid[col].idxmax()]
        return {"activity": row["activity"], "value": row[col], "sessions": int(row["sessions"])}

    return {
        "most_frequent": best("sessions"),
        "highest_strain": best("avg_strain"),
        "longest_duration": best("avg_duration"),
        "highest_calories": best("avg_calories"),
        "highest_hr": best("avg_hr"),
    }