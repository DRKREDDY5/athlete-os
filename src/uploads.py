"""
Upload validation & classification for "Analyze My WHOOP Data" mode.

Uploaded files are read directly from Streamlit's in-memory UploadedFile
buffers via pandas - never written to disk, never cached globally, never
logged. Processing is scoped to whatever calls these functions during the
active session; nothing here persists data beyond that.

Column requirements mirror exactly what src/data_loader.py's clean_* functions
and the rest of the analytics pipeline (metrics.py, analysis.py, training.py,
charts.py) actually access unconditionally - kept in sync deliberately so
validation reflects the real pipeline requirements, not a guess at them.
"""

import pandas as pd

PHYS_REQUIRED_COLUMNS = [
    "Cycle start time", "Cycle end time", "Recovery score %", "Day Strain",
    "Heart rate variability (ms)", "Resting heart rate (bpm)",
]
WORKOUTS_REQUIRED_COLUMNS = [
    "Cycle start time", "Workout start time", "Duration (min)", "Activity name",
    "Activity Strain", "Energy burned (cal)", "Average HR (bpm)", "Max HR (bpm)",
]
SLEEPS_REQUIRED_COLUMNS = [
    "Cycle start time", "Sleep onset", "Asleep duration (min)", "Nap",
]

REQUIRED_COLUMNS = {
    "physiological_cycles": PHYS_REQUIRED_COLUMNS,
    "workouts": WORKOUTS_REQUIRED_COLUMNS,
    "sleeps": SLEEPS_REQUIRED_COLUMNS,
}

DATASET_LABELS = {
    "physiological_cycles": "Physiological Cycles",
    "workouts": "Workouts",
    "sleeps": "Sleeps",
}


def read_uploaded_csv(uploaded_file) -> pd.DataFrame | None:
    """Read an uploaded file straight from its in-memory buffer. None if it isn't parseable as CSV."""
    if uploaded_file is None:
        return None
    try:
        return pd.read_csv(uploaded_file)
    except Exception:
        return None


def validate_upload(df: pd.DataFrame | None, expected_type: str) -> dict:
    """
    Validate an uploaded DataFrame against the schema required for
    `expected_type` ("physiological_cycles" | "workouts" | "sleeps").

    Schema-based, not filename-based: checks actual columns so a misplaced
    file (e.g. a workouts export presented as sleeps) gets a specific,
    actionable message rather than a silent misread or a crash.

    Returns: {"valid": bool, "missing": list[str], "best_guess": str | None}
    """
    if df is None:
        return {"valid": False, "missing": [], "best_guess": None}

    required = REQUIRED_COLUMNS[expected_type]
    missing = [c for c in required if c not in df.columns]
    if not missing:
        return {"valid": True, "missing": [], "best_guess": expected_type}

    # Doesn't match the expected schema - see if it matches a different
    # dataset type better, so the error message can say what it looks like.
    scores = {
        dtype: sum(1 for c in cols if c in df.columns) / len(cols)
        for dtype, cols in REQUIRED_COLUMNS.items()
    }
    best_guess = max(scores, key=scores.get)
    if scores[best_guess] < 0.5 or best_guess == expected_type:
        best_guess = None

    return {"valid": False, "missing": missing, "best_guess": best_guess}


def classify_dataset_type(df: pd.DataFrame) -> dict:
    """
    Determine which WHOOP export type (if any) a DataFrame's columns fully
    satisfy, independent of filename. Returns:
        {"type": str | None, "scores": {dtype: 0..1}}
    "type" is set only when the DataFrame contains every required column for
    exactly one dataset type; a DataFrame satisfying more than one schema at
    once (not expected with real WHOOP exports, but handled rather than
    guessed at) also comes back as unclassified with all matches available
    via "scores" for a best-guess message.
    """
    scores = {}
    exact_matches = []
    for dtype, cols in REQUIRED_COLUMNS.items():
        present = sum(1 for c in cols if c in df.columns)
        scores[dtype] = present / len(cols)
        if present == len(cols):
            exact_matches.append(dtype)

    dataset_type = exact_matches[0] if len(exact_matches) == 1 else None
    return {"type": dataset_type, "scores": scores}


def classify_uploads(files: list[tuple[str, "pd.DataFrame | None"]]) -> dict:
    """
    Classify a batch of uploaded (filename, DataFrame) pairs into the three
    required WHOOP export types, in any order, purely by schema.

    Returns:
        assigned: {dtype: (filename, df)} - one per uniquely, unambiguously
            classified required type
        duplicates: {dtype: [filenames]} - two or more files matched the
            same type; none of them is used, since picking one would be
            silently choosing arbitrary data
        unclassified: [(filename, best_guess_or_None)] - files matching no
            schema (or matching more than one, which we treat the same way:
            not confidently classifiable)
        unreadable: [filename] - couldn't even be parsed as CSV
        missing_types: [dtype] - required types with no valid assigned file
    """
    by_type: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    unclassified = []
    unreadable = []

    for filename, df in files:
        if df is None:
            unreadable.append(filename)
            continue

        result = classify_dataset_type(df)
        if result["type"]:
            by_type.setdefault(result["type"], []).append((filename, df))
            continue

        best = max(result["scores"], key=result["scores"].get)
        if result["scores"][best] < 0.5:
            best = None
        unclassified.append((filename, best))

    assigned = {}
    duplicates = {}
    for dtype, items in by_type.items():
        if len(items) == 1:
            assigned[dtype] = items[0]
        else:
            duplicates[dtype] = [fn for fn, _ in items]

    missing_types = [dtype for dtype in REQUIRED_COLUMNS if dtype not in assigned]

    return {
        "assigned": assigned,
        "duplicates": duplicates,
        "unclassified": unclassified,
        "unreadable": unreadable,
        "missing_types": missing_types,
    }
