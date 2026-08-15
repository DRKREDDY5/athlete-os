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

    # HR zone percentages are present in every Demo Athlete workout, but an
    # uploaded WHOOP export isn't guaranteed to include them - degrade to
    # "no zone profile available" rather than a KeyError.
    if not all(c in workouts.columns for c in ZONE_PCT_COLS):
        return pd.DataFrame(columns=cols)

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


def pick_top_activities(profile: pd.DataFrame, max_n: int = 3, min_sessions: int = MIN_SAMPLE_SIZE) -> list[str]:
    """
    Dynamically choose up to `max_n` activities for a generic "Your Training
    Comparison" section (used for uploaded data, where we can't assume any
    specific activity like Cricket exists) - primarily by session count,
    preferring activities that clear the small-sample threshold. Falls back
    to whatever exists if nothing clears that bar, so the section still
    shows something rather than staying empty.
    """
    if profile.empty:
        return []

    ranked = profile.sort_values("sessions", ascending=False)
    eligible = ranked[ranked["sessions"] >= min_sessions]
    if eligible.empty:
        eligible = ranked

    return eligible["activity"].head(max_n).tolist()


def filter_profile(profile: pd.DataFrame, activities: list[str]) -> pd.DataFrame:
    """Subset an activity profile to a specific list, preserving the given order, skipping absent ones."""
    present = [a for a in activities if a in profile["activity"].values]
    if not present:
        return profile.iloc[0:0]
    return profile.set_index("activity").loc[present].reset_index()


def _pair_note(a: pd.Series, b: pd.Series) -> str:
    """Combined small-sample caveat for a two-activity comparison sentence."""
    parts = [f"{r['activity']} n={int(r['sessions'])}" for r in (a, b) if r["sessions"] <= MIN_SAMPLE_SIZE]
    return f" (small sample: {', '.join(parts)})" if parts else ""


def small_sample_label(sessions: int) -> str:
    """Exact caution phrase used wherever a small-sample activity is called out."""
    return f"Small sample: {int(sessions)} sessions" if sessions <= MIN_SAMPLE_SIZE else ""


def generate_comparison_insights(profile: pd.DataFrame, max_insights: int = 3) -> list[str]:
    """
    Generic fallback: 2-3 deterministic sentences comparing the highest/lowest
    activities present in `profile` on strain, duration, and HR.
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
                f"**{lo['activity']}**{_pair_note(hi, lo)}."
            )

    valid_duration = profile.dropna(subset=["avg_duration"])
    if len(valid_duration) >= 2:
        hi = valid_duration.loc[valid_duration["avg_duration"].idxmax()]
        lo = valid_duration.loc[valid_duration["avg_duration"].idxmin()]
        if hi["activity"] != lo["activity"]:
            diff = hi["avg_duration"] - lo["avg_duration"]
            insights.append(
                f"**{hi['activity']}** sessions lasted {diff:.0f} minutes longer on average than "
                f"**{lo['activity']}**{_pair_note(hi, lo)}."
            )

    valid_hr = profile.dropna(subset=["avg_hr"])
    if len(valid_hr) >= 2:
        lo = valid_hr.loc[valid_hr["avg_hr"].idxmin()]
        note = small_sample_label(lo["sessions"])
        insights.append(
            f"**{lo['activity']}** showed the lowest average cardiovascular load among the compared "
            f"activities ({lo['avg_hr']:.0f} bpm avg HR)" + (f" ({note})" if note else "") + "."
        )

    return insights[:max_insights]


def generate_anchor_comparison_insights(profile: pd.DataFrame, anchor: str, max_insights: int = 3) -> list[str]:
    """
    Cricket-vs-Gym style comparisons: pit `anchor` (e.g. "Cricket") against
    each other activity present in `profile` on strain, duration, and HR,
    then keep the `max_insights` largest, most notable differences.

    Falls back to generic hi/lo comparisons if the anchor isn't present, so
    the section still says something useful when Cricket has no data in the
    selected period.
    """
    if anchor not in profile["activity"].values or len(profile) < 2:
        return generate_comparison_insights(profile, max_insights)

    anchor_row = profile[profile["activity"] == anchor].iloc[0]
    candidates = []  # (magnitude, sentence)

    for _, other in profile[profile["activity"] != anchor].iterrows():
        a_strain, o_strain = anchor_row["avg_strain"], other["avg_strain"]
        if pd.notna(a_strain) and pd.notna(o_strain) and min(a_strain, o_strain) > 0:
            diff_pct = (a_strain - o_strain) / o_strain * 100
            hi, lo = (anchor_row, other) if diff_pct > 0 else (other, anchor_row)
            candidates.append((
                abs(diff_pct),
                f"**{hi['activity']}** produced {abs(diff_pct):.0f}% higher average strain than "
                f"**{lo['activity']}**{_pair_note(hi, lo)}.",
            ))

        a_dur, o_dur = anchor_row["avg_duration"], other["avg_duration"]
        if pd.notna(a_dur) and pd.notna(o_dur) and abs(a_dur - o_dur) >= 1:
            diff = a_dur - o_dur
            hi, lo = (anchor_row, other) if diff > 0 else (other, anchor_row)
            candidates.append((
                abs(diff),
                f"**{hi['activity']}** sessions lasted {abs(diff):.0f} minutes longer on average than "
                f"**{lo['activity']}**{_pair_note(hi, lo)}.",
            ))

        a_hr, o_hr = anchor_row["avg_hr"], other["avg_hr"]
        if pd.notna(a_hr) and pd.notna(o_hr) and a_hr != o_hr:
            hi, lo = (anchor_row, other) if a_hr > o_hr else (other, anchor_row)
            candidates.append((
                abs(a_hr - o_hr),
                f"**{lo['activity']}** showed lower average cardiovascular load than **{hi['activity']}** "
                f"({lo['avg_hr']:.0f} vs {hi['avg_hr']:.0f} bpm avg HR)"
                f"{_pair_note(lo, hi)}.",
            ))

    candidates.sort(key=lambda c: c[0], reverse=True)
    # Keep each metric type at most once so the top N insights stay varied.
    seen_kinds = set()
    picked = []
    for _, sentence in candidates:
        kind = "strain" if "strain" in sentence else "minutes longer" if "minutes longer" in sentence else "cardio"
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        picked.append(sentence)
        if len(picked) >= max_insights:
            break

    return picked


def identify_cvg_leaders(profile: pd.DataFrame) -> dict:
    """
    For a small activity profile (e.g. Cricket vs Gym), identify which
    activity leads on avg_strain (highest), avg_duration (highest), and
    avg_hr (lowest - i.e. lowest cardiovascular load). Used purely to
    highlight the standout stat on each activity's comparison card; returns
    {} when there's nothing meaningful to compare (fewer than 2 activities).
    """
    if len(profile) < 2:
        return {}

    leaders = {}
    if profile["avg_strain"].notna().any():
        leaders["avg_strain"] = profile.loc[profile["avg_strain"].idxmax(), "activity"]
    if profile["avg_duration"].notna().any():
        leaders["avg_duration"] = profile.loc[profile["avg_duration"].idxmax(), "activity"]
    if profile["avg_hr"].notna().any():
        leaders["avg_hr"] = profile.loc[profile["avg_hr"].idxmin(), "activity"]
    return leaders


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