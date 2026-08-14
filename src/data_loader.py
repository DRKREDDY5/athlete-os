"""
Data loading & cleaning for Athlete OS.

Reads the three raw WHOOP export CSVs and returns cleaned DataFrames.
The original CSV files are never written to - all cleaning happens in memory.
"""

import io
import os

import pandas as pd
import streamlit as st

DATA_DIR = "."  # CSVs live alongside app.py, when present locally

# A workout longer than this is treated as a tracking error (forgot to stop
# the activity) and excluded from duration-based averages. Identified during
# EDA: a single "Functional Fitness" session logged at 746 minutes.
DURATION_OUTLIER_MINUTES = 300


def _read_csv(filename: str) -> pd.DataFrame:
    """
    Read a WHOOP export CSV from local disk if present (local development).
    Otherwise fall back to Streamlit Secrets under the same key, minus the
    ".csv" extension (cloud deployment) - this keeps personal WHOOP data out
    of the public GitHub repo entirely: locally it's a gitignored file next
    to app.py, and on Streamlit Community Cloud it lives only in that app's
    encrypted Secrets, never in git.
    """
    local_path = f"{DATA_DIR}/{filename}"
    if os.path.exists(local_path):
        return pd.read_csv(local_path)

    secret_key = filename.removesuffix(".csv")
    if secret_key in st.secrets:
        return pd.read_csv(io.StringIO(st.secrets[secret_key]))

    raise FileNotFoundError(
        f"Could not find {filename} locally, and no '{secret_key}' entry exists in Streamlit Secrets. "
        f"For local development, place {filename} next to app.py. For a cloud deployment, add a "
        f"'{secret_key}' secret containing the CSV's full text."
    )


@st.cache_data
def load_physiological_cycles() -> pd.DataFrame:
    df = _read_csv("physiological_cycles.csv")
    df["Cycle start time"] = pd.to_datetime(df["Cycle start time"])
    df["date"] = df["Cycle start time"].dt.date

    # Drop cycles with no usable data at all (e.g. the very first bootstrap
    # row before tracking began). A cycle is "empty" if it has neither a
    # recovery score nor a day strain value.
    has_signal = df["Recovery score %"].notna() | df["Day Strain"].notna()
    df = df[has_signal].reset_index(drop=True)

    # An "open" cycle is today's in-progress WHOOP day: it has no Cycle end
    # time yet, so Day Strain (and anything else that only finalizes at
    # cycle close) is incomplete and would understate strain-based averages
    # if included. Recovery/HRV/RHR are morning measurements taken at wake-up
    # and are still valid even while the cycle is open, so we flag rather
    # than drop the row.
    df["is_open_cycle"] = df["Cycle end time"].isna()

    return df


@st.cache_data
def load_workouts() -> pd.DataFrame:
    df = _read_csv("workouts.csv")
    df["Workout start time"] = pd.to_datetime(df["Workout start time"])
    df["Cycle start time"] = pd.to_datetime(df["Cycle start time"])
    # Use the cycle date (the WHOOP "day") so a workout joins to the same
    # day's recovery/sleep data, matching physiological_cycles.csv.
    df["date"] = df["Cycle start time"].dt.date

    # Flag (don't drop) the duration outlier so it still counts toward
    # workout totals and activity-type breakdowns, just not duration averages.
    df["duration_is_outlier"] = df["Duration (min)"] > DURATION_OUTLIER_MINUTES

    return df


@st.cache_data
def load_sleeps() -> pd.DataFrame:
    df = _read_csv("sleeps.csv")
    df["Sleep onset"] = pd.to_datetime(df["Sleep onset"])
    df["Cycle start time"] = pd.to_datetime(df["Cycle start time"])
    df["date"] = df["Cycle start time"].dt.date

    # Main sleep vs naps: naps are short, low-performance top-ups and should
    # not be blended into "primary sleep" metrics.
    df["is_nap"] = df["Nap"].astype(bool)

    return df


def filter_by_date(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Filter a cleaned DataFrame (must have a 'date' column) to [start_date, end_date]."""
    if df.empty:
        return df
    mask = (df["date"] >= start_date) & (df["date"] <= end_date)
    return df[mask]


def get_overall_date_bounds(phys: pd.DataFrame, workouts: pd.DataFrame, sleeps: pd.DataFrame):
    """Earliest and latest date across all three cleaned datasets."""
    all_dates = pd.concat([
        phys["date"], workouts["date"], sleeps["date"]
    ])
    return all_dates.min(), all_dates.max()
