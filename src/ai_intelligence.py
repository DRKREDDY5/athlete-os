"""
Athlete OS Intelligence: a grounded conversational interpretation layer on
top of Athlete OS's existing deterministic analytics.

Architecture:
    question -> Athlete OS's own deterministic analysis functions
             -> compact structured context (already-validated numbers)
             -> Groq LLM
             -> natural-language interpretation

The LLM never computes a metric and never sees raw WHOOP rows. It receives
only a small JSON summary built from numbers this app already computed
elsewhere (compute_kpis, compute_recovery_drivers, compute_activity_profile,
etc.) - it interprets and explains them, it does not derive them.
"""

import json

import pandas as pd
import streamlit as st

from src.metrics import compute_kpis, generate_snapshot, get_performance_trend_label
from src.analysis import compute_recovery_drivers, key_recovery_insight
from src.training import compute_activity_profile, compute_hr_zone_profile, training_summary, pick_top_activities

MAX_QUESTIONS_PER_SESSION = 8
DEFAULT_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile is being deprecated on Groq's free/dev tier (2026-08-16)

SYSTEM_PROMPT = """You are Athlete OS Intelligence, an interpretation layer over a personal WHOOP performance analytics dashboard called Athlete OS.

You are given a JSON summary of already-computed, validated metrics for the athlete's currently selected date range. You did NOT calculate any of these numbers - Athlete OS's own deterministic pandas analytics did, and they are correct and already validated. Your only job is to interpret and explain them in clear, concise natural language for the athlete asking the question.

Rules you must follow exactly:
- Never invent, estimate, guess, or recompute a number. Only reference numbers present in the provided JSON context. If something isn't in the context, say the data isn't available for that rather than guessing.
- If the context marks a relationship as not having sufficient data, say so plainly - do not fabricate a value or interpretation for it.
- Use careful, non-causal language: "associated with", "appears", "in this dataset", "observed relationship", "historically". Never state or imply that one variable causes another.
- Never give medical advice. Never prescribe medication, supplements, sleep treatments, or injury treatment. Never issue directives like "you should sleep exactly 8 hours" or "you should train harder."
- For training questions, describe what the data shows rather than prescribing an "optimal" training plan.
- Keep answers concise: roughly 80-180 words, evidence-based, and directly responsive to the question.
- This is fitness/performance data exploration, not medical advice - do not present it as either.
"""

RECOVERY_KEYWORDS = ["recovery", "correlat", "driver", "influence", "hrv", "resting heart", " rhr", "affects my sleep"]


def is_ai_available() -> bool:
    """True only if a Groq API key is configured via Streamlit Secrets - never hardcoded."""
    try:
        return bool(st.secrets.get("GROQ_API_KEY"))
    except Exception:
        return False


def _get_client():
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None
    if not api_key:
        return None
    from groq import Groq
    return Groq(api_key=api_key)


def _get_model() -> str:
    try:
        return st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)
    except Exception:
        return DEFAULT_MODEL


def _round(value, decimals: int = 1):
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def suggested_questions(is_uploaded_mode: bool) -> list[str]:
    """Context-aware suggested questions - never assumes Cricket exists for uploaded data."""
    if is_uploaded_mode:
        return [
            "Summarize my performance",
            "What stands out in my recovery?",
            "Compare my top activities",
            "What changed over time?",
        ]
    return [
        "Summarize my performance",
        "What drives my recovery?",
        "Compare Cricket vs gym",
        "What changed over time?",
    ]


def build_context(
    phys: pd.DataFrame, workouts: pd.DataFrame, sleeps: pd.DataFrame,
    start_date, end_date, data_source_label: str, is_uploaded_mode: bool,
) -> dict:
    """
    Assemble a compact, fully-deterministic, JSON-able summary of the active
    dataset/date range using Athlete OS's existing analytics functions.
    Contains no raw WHOOP rows - only already-computed aggregates - and this
    dict (not raw CSV data) is exactly what gets sent to the LLM.
    """
    kpis = compute_kpis(phys, workouts, sleeps, start_date, end_date)
    trend_label = get_performance_trend_label(phys)
    drivers = compute_recovery_drivers(phys, sleeps)
    observations = generate_snapshot(phys, workouts, start_date, end_date)
    profile = compute_activity_profile(workouts)
    zone_profile = compute_hr_zone_profile(workouts)
    summary = training_summary(profile)

    if is_uploaded_mode:
        comparison_activities = pick_top_activities(profile, max_n=3)
        comparison_title = "Your Training Comparison"
    else:
        comparison_activities = ["Cricket", "Functional Fitness", "Strength Trainer"]
        comparison_title = "Cricket vs Gym Training"

    return {
        "data_source": data_source_label,
        "date_range": {"start": str(start_date), "end": str(end_date)},
        "kpis": {
            "days_tracked": kpis["days_tracked"],
            "total_workouts": kpis["total_workouts"],
            "avg_recovery_pct": _round(kpis["avg_recovery"]),
            "avg_hrv_ms": _round(kpis["avg_hrv"]),
            "avg_resting_hr_bpm": _round(kpis["avg_rhr"]),
            "avg_sleep_hours": _round(kpis["avg_sleep_hours"], 2),
            "avg_day_strain": _round(kpis["avg_day_strain"]),
            "sessions_per_week": _round(kpis["sessions_per_week"]),
        },
        "observed_performance_trend": trend_label,
        "recovery_relationships": [
            {
                "driver": d["label"],
                "r": round(d["r"], 2) if d["r"] is not None else None,
                "n": d["n"],
                "strength": d["strength"],
                "direction": d["direction"],
                "sufficient_data": not d["insufficient"],
            }
            for d in drivers
        ],
        "key_recovery_insight": key_recovery_insight(drivers),
        "deterministic_observations": [f"{cat}: {text}" for cat, text in observations],
        "activity_profile": [
            {
                "activity": row["activity"],
                "sessions": int(row["sessions"]),
                "avg_strain": _round(row["avg_strain"]),
                "avg_duration_min": _round(row["avg_duration"]),
                "avg_calories": _round(row["avg_calories"]),
                "avg_hr_bpm": _round(row["avg_hr"]),
                "avg_max_hr_bpm": _round(row["avg_max_hr"]),
            }
            for _, row in profile.head(8).iterrows()
        ] if not profile.empty else [],
        "training_summary": {
            k: {"activity": v["activity"], "value": _round(v["value"]), "sessions": v["sessions"]}
            for k, v in summary.items() if v
        },
        "hr_zone_profile_available": not zone_profile.empty,
        "signature_comparison": {
            "title": comparison_title,
            "activities": comparison_activities,
        },
    }


def _insufficient_recovery_data_answer(question: str, context: dict) -> str | None:
    """
    If Athlete OS itself has already determined there's insufficient data
    for a recovery-flavored question, return the deterministic explanation
    directly rather than asking the LLM to manufacture an answer.
    """
    q = question.lower()
    if any(k in q for k in RECOVERY_KEYWORDS):
        if all(not d["sufficient_data"] for d in context["recovery_relationships"]):
            return (
                "There are not enough valid paired observations in this selected period to analyze "
                "recovery relationships. Try Last 30 Days, Last 90 Days, or All Data."
            )
    return None


def ask_question(question: str, context: dict) -> dict:
    """
    Answer a free-text question grounded in `context`.
    Returns {"ok": bool, "answer": str | None, "error": str | None, "deterministic_only": bool}.
    "error" is one of: "not_configured", "api_error" (never a raw exception/stack trace).
    """
    guard = _insufficient_recovery_data_answer(question, context)
    if guard:
        return {"ok": True, "answer": guard, "error": None, "deterministic_only": True}

    client = _get_client()
    if client is None:
        return {"ok": False, "answer": None, "error": "not_configured", "deterministic_only": False}

    user_content = (
        f"Question: {question}\n\n"
        "Athlete OS context (JSON, already validated by deterministic analytics - use only this):\n"
        f"{json.dumps(context, default=str)}"
    )

    try:
        completion = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        answer = completion.choices[0].message.content.strip()
        return {"ok": True, "answer": answer, "error": None, "deterministic_only": False}
    except Exception:
        return {"ok": False, "answer": None, "error": "api_error", "deterministic_only": False}


def generate_brief(context: dict) -> dict:
    """
    Ask for a short structured brief (PERFORMANCE / RECOVERY / TRAINING /
    KEY OBSERVATIONS) grounded in `context`. Same failure modes as ask_question.
    """
    client = _get_client()
    if client is None:
        return {"ok": False, "text": None, "error": "not_configured"}

    prompt = (
        "Generate a short performance brief for this athlete's selected period using ONLY the "
        "provided context. Use exactly these four section headers (all caps, each on its own line), "
        "with 1-3 sentences under each:\n\n"
        "PERFORMANCE\nRECOVERY\nTRAINING\nKEY OBSERVATIONS\n\n"
        f"Athlete OS context (JSON):\n{json.dumps(context, default=str)}"
    )

    try:
        completion = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        text = completion.choices[0].message.content.strip()
        return {"ok": True, "text": text, "error": None}
    except Exception:
        return {"ok": False, "text": None, "error": "api_error"}


def recovery_evidence_rows(context: dict) -> list[dict]:
    """Deterministic evidence rows for the 'Evidence Used' panel - sourced directly from `context`, never from the LLM's own text."""
    return context["recovery_relationships"]


def format_brief_as_markdown(context: dict, brief_text: str) -> str:
    """Downloadable .md version of a generated brief - summarized metrics only, no raw WHOOP records."""
    lines = [
        "# Athlete OS Intelligence — Performance Brief",
        "",
        f"**Data source:** {context['data_source']}  ",
        f"**Period:** {context['date_range']['start']} to {context['date_range']['end']}",
        "",
        brief_text,
        "",
        "---",
        "",
        "## Evidence Used",
        "",
        "| Relationship | r | N | Strength |",
        "|---|---|---|---|",
    ]
    for row in context["recovery_relationships"]:
        r_str = f"{row['r']:+.2f}" if row["r"] is not None else "N/A"
        strength = row["strength"] or "Insufficient data"
        lines.append(f"| {row['driver']} → Recovery | {r_str} | {row['n']} | {strength} |")
    lines += [
        "",
        "_Correlations describe association, not causation. This is fitness-data exploration, not medical advice._",
    ]
    return "\n".join(lines)
