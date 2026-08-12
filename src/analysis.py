"""
Recovery Driver Lab analysis: correlations between recovery and its
candidate drivers (prior-day strain, sleep duration, HRV, resting HR).

All results are observational — "associated with" / "correlated with",
never causal or medical language. Every function operates on whatever
date-filtered DataFrame is passed in; nothing is hard-coded.
"""

import pandas as pd

MIN_OBSERVATIONS = 5


def safe_correlation(x: pd.Series, y: pd.Series) -> dict:
    """
    Pearson correlation between two series, pairwise-aligned and NaN-dropped.

    Returns a dict with:
        r        - correlation coefficient, or None if not computable
        n        - number of valid paired observations
        reason   - None if r was computed, otherwise why it wasn't
                   ("insufficient_data" | "zero_variance")
    """
    paired = pd.concat([x, y], axis=1).dropna()
    n = len(paired)

    if n < MIN_OBSERVATIONS:
        return {"r": None, "n": n, "reason": "insufficient_data"}

    xs, ys = paired.iloc[:, 0], paired.iloc[:, 1]
    if xs.std(ddof=0) == 0 or ys.std(ddof=0) == 0:
        return {"r": None, "n": n, "reason": "zero_variance"}

    r = xs.corr(ys)
    if pd.isna(r):
        return {"r": None, "n": n, "reason": "nan"}

    return {"r": float(r), "n": n, "reason": None}


def classify_strength(r: float) -> str:
    """Deterministic |r| -> qualitative strength label."""
    a = abs(r)
    if a < 0.2:
        return "Very weak"
    elif a < 0.4:
        return "Weak"
    elif a < 0.6:
        return "Moderate"
    elif a < 0.8:
        return "Strong"
    else:
        return "Very strong"


MAX_CYCLE_GAP_HOURS = 6  # tolerance for the handoff between one cycle's end and the next one's start


def build_prior_strain_dataset(phys: pd.DataFrame) -> pd.DataFrame:
    """
    Align each completed cycle's Day Strain with the RECOVERY SCORE OF THE
    FOLLOWING CYCLE (not same-row recovery), using the genuinely next WHOOP
    cycle rather than assuming the next DataFrame row is automatically it.

    Rule: sort cycles chronologically, take Day Strain from a cycle only if
    that cycle is complete (is_open_cycle == False, since strain isn't final
    until the cycle closes), and pair it with the Recovery score % of the
    next row in the sorted sequence ONLY IF that next row's Cycle start time
    begins within MAX_CYCLE_GAP_HOURS of the current cycle's Cycle end time.
    A larger gap means there's a tracking break between the two rows (e.g. the
    watch wasn't worn) - that "next" row is not really the next WHOOP cycle,
    so the pair is excluded rather than silently treated as consecutive.
    (Recovery from an open/current cycle is still eligible as a "next
    recovery" value, since recovery is a wake-time measurement that's valid
    even mid-cycle.)

    Returns columns: previous_cycle_date, previous_day_strain,
    recovery_date, next_recovery_score.
    """
    d = phys.sort_values("Cycle start time").reset_index(drop=True)
    cycle_end = pd.to_datetime(d["Cycle end time"])
    next_start = d["Cycle start time"].shift(-1)
    gap_hours = (next_start - cycle_end).dt.total_seconds() / 3600
    is_consecutive = gap_hours.abs() <= MAX_CYCLE_GAP_HOURS

    out = pd.DataFrame({
        "previous_cycle_date": d["date"],
        "previous_day_strain": d["Day Strain"].where(~d["is_open_cycle"] & is_consecutive),
        "recovery_date": d["date"].shift(-1),
        "next_recovery_score": d["Recovery score %"].shift(-1),
    })

    out = out.dropna(subset=["previous_day_strain", "next_recovery_score"]).reset_index(drop=True)
    return out


def build_sleep_recovery_frame(phys: pd.DataFrame, sleeps: pd.DataFrame) -> pd.DataFrame:
    """Main-sleep-only (naps excluded) hours joined to same-day recovery."""
    main_sleep = sleeps[~sleeps["is_nap"]][["date", "Asleep duration (min)"]].copy()
    main_sleep = main_sleep.groupby("date", as_index=False)["Asleep duration (min)"].mean()

    d = phys[["date", "Cycle start time", "Recovery score %"]].merge(main_sleep, on="date", how="inner")
    d["sleep_hours"] = d["Asleep duration (min)"] / 60
    return d.dropna(subset=["sleep_hours", "Recovery score %"])


def _interpretation(x_label: str, y_label: str, r: float, strength: str) -> str:
    direction = "positive" if r > 0 else "negative"
    return (
        f"Higher {x_label} showed a {strength.lower()} {direction} association "
        f"with {y_label} in the selected period (r = {r:+.2f})."
    )


def compute_recovery_drivers(phys: pd.DataFrame, sleeps: pd.DataFrame) -> list[dict]:
    """
    Compute all four recovery-driver relationships and return them ranked by
    descending |r| (relationships with no valid r sort last).

    Each entry: key, label, x_label, y_label, unit, chart_df (date/x/y),
    r, n, strength, direction, interpretation, insufficient (bool).
    """
    drivers = []

    # --- Previous-day strain -> next recovery ---
    strain_df = build_prior_strain_dataset(phys)
    result = safe_correlation(strain_df["previous_day_strain"], strain_df["next_recovery_score"])
    drivers.append({
        "key": "prev_strain",
        "label": "Previous-Day Strain",
        "x_label": "previous-day strain",
        "y_label": "next-day recovery",
        "axis_x": "Previous-Day Strain",
        "axis_y": "Next Recovery %",
        "unit": "",
        "chart_df": pd.DataFrame({
            "date": strain_df["recovery_date"],
            "x": strain_df["previous_day_strain"],
            "y": strain_df["next_recovery_score"],
        }),
        **result,
    })

    # --- Sleep duration -> recovery ---
    sleep_df = build_sleep_recovery_frame(phys, sleeps)
    result = safe_correlation(sleep_df["sleep_hours"], sleep_df["Recovery score %"])
    drivers.append({
        "key": "sleep",
        "label": "Sleep Duration",
        "x_label": "sleep duration",
        "y_label": "recovery",
        "axis_x": "Sleep Duration (hrs)",
        "axis_y": "Recovery %",
        "unit": "hrs",
        "chart_df": pd.DataFrame({
            "date": sleep_df["Cycle start time"],
            "x": sleep_df["sleep_hours"],
            "y": sleep_df["Recovery score %"],
        }),
        **result,
    })

    # --- HRV -> recovery ---
    hrv_df = phys[["date", "Cycle start time", "Heart rate variability (ms)", "Recovery score %"]].dropna(
        subset=["Heart rate variability (ms)", "Recovery score %"]
    )
    result = safe_correlation(hrv_df["Heart rate variability (ms)"], hrv_df["Recovery score %"])
    drivers.append({
        "key": "hrv",
        "label": "HRV",
        "x_label": "HRV",
        "y_label": "recovery",
        "axis_x": "HRV (ms)",
        "axis_y": "Recovery %",
        "unit": "ms",
        "chart_df": pd.DataFrame({
            "date": hrv_df["Cycle start time"],
            "x": hrv_df["Heart rate variability (ms)"],
            "y": hrv_df["Recovery score %"],
        }),
        **result,
    })

    # --- Resting HR -> recovery ---
    rhr_df = phys[["date", "Cycle start time", "Resting heart rate (bpm)", "Recovery score %"]].dropna(
        subset=["Resting heart rate (bpm)", "Recovery score %"]
    )
    result = safe_correlation(rhr_df["Resting heart rate (bpm)"], rhr_df["Recovery score %"])
    drivers.append({
        "key": "rhr",
        "label": "Resting Heart Rate",
        "x_label": "resting heart rate",
        "y_label": "recovery",
        "axis_x": "Resting HR (bpm)",
        "axis_y": "Recovery %",
        "unit": "bpm",
        "chart_df": pd.DataFrame({
            "date": rhr_df["Cycle start time"],
            "x": rhr_df["Resting heart rate (bpm)"],
            "y": rhr_df["Recovery score %"],
        }),
        **result,
    })

    # Finalize strength/direction/interpretation for valid results
    for d in drivers:
        if d["r"] is not None:
            d["strength"] = classify_strength(d["r"])
            d["direction"] = "positive" if d["r"] > 0 else "negative"
            d["interpretation"] = _interpretation(d["x_label"], d["y_label"], d["r"], d["strength"])
            d["insufficient"] = False
        else:
            d["strength"] = None
            d["direction"] = None
            d["interpretation"] = "Not enough data to calculate a reliable relationship for this period."
            d["insufficient"] = True

    drivers.sort(key=lambda d: abs(d["r"]) if d["r"] is not None else -1, reverse=True)
    return drivers


def key_recovery_insight(drivers: list[dict]) -> str:
    """One deterministic sentence naming the strongest valid relationship."""
    valid = [d for d in drivers if not d["insufficient"]]
    if not valid:
        return "Not enough data in this period to identify a reliable recovery driver."

    top = valid[0]
    direction_word = "higher" if top["r"] > 0 else "lower"
    return (
        f"**{top['label']}** showed the strongest relationship with recovery during this period "
        f"(r = {top['r']:+.2f}). Higher {top['x_label']} values were generally associated with "
        f"{direction_word} recovery scores."
    )