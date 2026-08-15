"""
Athlete OS - Personal Performance Intelligence Dashboard
Iteration 6: Premium sportive UI / visual design upgrade.

Run with: streamlit run app.py
"""

import datetime as dt

import pandas as pd
import streamlit as st

from src.data_loader import (
    load_physiological_cycles, load_workouts, load_sleeps,
    clean_physiological_cycles, clean_workouts, clean_sleeps,
    filter_by_date, get_overall_date_bounds,
)
from src.uploads import read_uploaded_csv, classify_uploads, DATASET_LABELS
from src.metrics import (
    compute_kpis, generate_snapshot, get_performance_trend_label,
    trend_direction, recovery_band_label,
)
from src.charts import (
    recovery_trend_chart, hrv_trend_chart, rhr_trend_chart, workout_breakdown_chart,
    driver_scatter_chart, intensity_profile_chart, hr_zone_stacked_chart,
    weekly_sessions_chart, weekly_strain_chart, COLOR_BLUE,
)
from src.analysis import compute_recovery_drivers, key_recovery_insight
from src.training import (
    MIN_SAMPLE_SIZE, compute_activity_profile, compute_training_kpis,
    compute_hr_zone_profile, compute_weekly_training_volume, filter_profile,
    generate_anchor_comparison_insights, training_summary, small_sample_label,
    identify_cvg_leaders, pick_top_activities,
)
from src.theme import (
    inject_theme, mdbold, render_insight_card, render_eyebrow, render_hero, metric_context_html,
)
from src.ai_intelligence import (
    is_ai_available, suggested_questions, build_context, ask_question, generate_brief,
    recovery_evidence_rows, format_brief_as_markdown, MAX_QUESTIONS_PER_SESSION,
)

st.set_page_config(page_title="Athlete OS", page_icon="📊", layout="wide")
inject_theme()

# ============================================================
# DATA SOURCE
# ============================================================
if "data_source" not in st.session_state:
    st.session_state.data_source = "Demo Athlete"
if "_prev_data_source" not in st.session_state:
    st.session_state._prev_data_source = st.session_state.data_source

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.05rem; font-weight:800; letter-spacing:-0.01em; color:var(--aos-text); '
        'margin-bottom:0;">ATHLETE OS</div>'
        '<div style="font-size:0.7rem; font-weight:700; letter-spacing:.12em; color:var(--aos-muted); '
        'text-transform:uppercase; margin-bottom:18px;">Performance Lab</div>',
        unsafe_allow_html=True,
    )

    render_eyebrow("Data Source")
    st.radio(
        "Data Source", ["Demo Athlete", "Analyze My WHOOP Data"],
        key="data_source", label_visibility="collapsed",
    )
    if st.session_state.data_source == "Demo Athlete":
        st.caption("Explore Athlete OS using the built-in performance dataset.")
    else:
        st.caption("Upload your own WHOOP exports and generate your personal analysis.")
    st.write("")

data_source = st.session_state.data_source
is_uploaded_mode = data_source == "Analyze My WHOOP Data"

# Switching data sources invalidates any date range picked for the previous
# dataset - drop it so the app re-derives fresh bounds for whichever
# dataset is now active, instead of leaving one athlete's range applied to
# another's data.
if data_source != st.session_state._prev_data_source:
    st.session_state.pop("start_date", None)
    st.session_state.pop("end_date", None)
    st.session_state._prev_data_source = data_source


if "upload_widget_version" not in st.session_state:
    st.session_state.upload_widget_version = 0


def render_upload_panel():
    """
    Main-area upload flow for "Analyze My WHOOP Data": a single multi-file
    uploader, automatic schema-based classification (order-independent, not
    filename-based), a concise privacy note, and a readiness summary once
    all three required types are unambiguously identified. Uploaded files
    are read straight from Streamlit's in-memory buffers via pandas - never
    written to disk, never added to any cache shared across sessions/users,
    never logged. Returns (phys, workouts, sleeps, ready).
    """
    render_eyebrow("Analyze My WHOOP Data")
    st.markdown("#### Upload Your WHOOP Exports")
    st.caption(
        "Your uploaded files are analyzed for the current app session and are "
        "not added to the public Athlete OS repository."
    )

    uploaded_files = st.file_uploader(
        "Upload your WHOOP exports", type="csv", accept_multiple_files=True,
        key=f"whoop_uploads_{st.session_state.upload_widget_version}",
        help="Select your Physiological Cycles, Workouts, and Sleeps CSV exports together, in any order.",
    )

    if uploaded_files:
        clear_col, _ = st.columns([1, 4])
        with clear_col:
            if st.button("Clear uploaded data", use_container_width=True):
                # Swapping the uploader's key forces Streamlit to mount a
                # fresh, empty widget rather than mutating shared state. Also
                # drop the date range so a subsequent upload of different
                # data doesn't inherit stale bounds from what was cleared.
                st.session_state.upload_widget_version += 1
                st.session_state.pop("start_date", None)
                st.session_state.pop("end_date", None)
                st.rerun()

    if not uploaded_files:
        st.info("Upload your three WHOOP export files (Physiological Cycles, Workouts, Sleeps) to generate your personal analysis.")
        return None, None, None, False

    files = [(f.name, read_uploaded_csv(f)) for f in uploaded_files]
    result = classify_uploads(files)

    render_eyebrow("WHOOP Exports")
    for dtype, label in DATASET_LABELS.items():
        if dtype in result["assigned"]:
            filename, df = result["assigned"][dtype]
            st.success(f"✓ {label} — {len(df)} records ({filename})")
        elif dtype in result["duplicates"]:
            st.error(
                f"✗ {label}: {len(result['duplicates'][dtype])} uploaded files all look like a "
                f"{label} export ({', '.join(result['duplicates'][dtype])}) - upload only one."
            )
        else:
            st.warning(f"○ {label}: not yet identified.")

    for filename, best_guess in result["unclassified"]:
        if best_guess:
            st.error(
                f"Could not identify **{filename}** as a supported WHOOP export "
                f"(closest match: {DATASET_LABELS[best_guess]}, but required columns are missing)."
            )
        else:
            st.error(
                f"Could not identify **{filename}** as a supported WHOOP export. "
                f"Supported types: {', '.join(DATASET_LABELS.values())}."
            )

    for filename in result["unreadable"]:
        st.error(f"**{filename}** could not be read as a CSV file.")

    if result["missing_types"]:
        missing_labels = [DATASET_LABELS[t] for t in result["missing_types"]]
        st.markdown("**Missing:**\n" + "\n".join(f"- {label} export" for label in missing_labels))
        return None, None, None, False

    phys_raw = result["assigned"]["physiological_cycles"][1]
    workouts_raw = result["assigned"]["workouts"][1]
    sleeps_raw = result["assigned"]["sleeps"][1]

    try:
        phys = clean_physiological_cycles(phys_raw)
        workouts = clean_workouts(workouts_raw)
        sleeps = clean_sleeps(sleeps_raw)
    except Exception as e:
        st.error(f"Could not process the uploaded files: {e}")
        return None, None, None, False

    min_d, max_d = get_overall_date_bounds(phys, workouts, sleeps)
    st.markdown(
        f'<div class="aos-signal-card"><div class="aos-eyebrow" style="color:var(--aos-green);">'
        f'WHOOP Data Ready ✓</div>'
        f'{len(phys)} physiological records · {len(workouts)} workouts · {len(sleeps)} sleep records<br>'
        f'Date range: {min_d:%b %d, %Y} – {max_d:%b %d, %Y}</div>',
        unsafe_allow_html=True,
    )

    return phys, workouts, sleeps, True


# ---------- Load & clean data ----------
if is_uploaded_mode:
    phys_all, workouts_all, sleeps_all, data_ready = render_upload_panel()
    if not data_ready:
        st.stop()
else:
    phys_all = load_physiological_cycles()
    workouts_all = load_workouts()
    sleeps_all = load_sleeps()
min_date, max_date = get_overall_date_bounds(phys_all, workouts_all, sleeps_all)

# ---------- Sidebar: date range controls ----------
# Default/initial state is always the full available dataset range (dynamic,
# never hard-coded), so the app opens with a fully populated dashboard.
if "start_date" not in st.session_state:
    st.session_state.start_date = min_date
    st.session_state.end_date = max_date


def _set_range(days: int | None):
    st.session_state.end_date = max_date
    st.session_state.start_date = max_date if days is None else max(min_date, max_date - dt.timedelta(days=days - 1))
    if days is None:
        st.session_state.start_date = min_date


def _active_range_label(start_date, end_date) -> str:
    """
    Which quick-range option (if any) the current start/end dates match,
    derived directly from the dates themselves rather than a separately
    tracked flag - so it can never drift out of sync with what's actually
    selected, and a manual date edit is automatically detected as Custom.
    """
    if start_date == min_date and end_date == max_date:
        return "All data"
    if end_date == max_date:
        for label, days in [("Last 7 days", 7), ("Last 30 days", 30), ("Last 90 days", 90)]:
            if start_date == max(min_date, max_date - dt.timedelta(days=days - 1)):
                return label
    return "Custom range"


with st.sidebar:
    render_eyebrow("Date Range")
    active_label = _active_range_label(st.session_state.start_date, st.session_state.end_date)

    quick_ranges = [("Last 7 days", 7), ("Last 30 days", 30), ("Last 90 days", 90), ("All data", None)]
    col1, col2 = st.columns(2)
    for i, (label, days) in enumerate(quick_ranges):
        target_col = col1 if i % 2 == 0 else col2
        is_active = active_label == label
        with target_col:
            if st.button(("● " if is_active else "") + label, use_container_width=True,
                         type="primary" if is_active else "secondary"):
                _set_range(days)

    st.write("")
    render_eyebrow("Custom Range")
    st.date_input("Start date", key="start_date", min_value=min_date, max_value=max_date)
    st.date_input("End date", key="end_date", min_value=min_date, max_value=max_date)

    if active_label == "Custom range":
        st.caption("● Custom range")

start_date, end_date = st.session_state.start_date, st.session_state.end_date


def fmt(value, suffix="", decimals=0):
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}{suffix}"


# ---------- Empty range guard ----------
if start_date > end_date:
    st.title("Athlete OS")
    st.warning("Start date is after end date. Please adjust the date range in the sidebar.")
    st.stop()

phys = filter_by_date(phys_all, start_date, end_date)
workouts = filter_by_date(workouts_all, start_date, end_date)
sleeps = filter_by_date(sleeps_all, start_date, end_date)

if phys.empty and workouts.empty and sleeps.empty:
    st.title("Athlete OS")
    st.info("No data available in the selected date range. Try widening the range in the sidebar.")
    st.stop()

days_tracked = phys["date"].nunique()

# Computed once, shared by the hero's Key Insight and the Recovery Lab tab.
drivers = compute_recovery_drivers(phys, sleeps)
hero_insight_text = key_recovery_insight(drivers)
if hero_insight_text.startswith("Not enough data"):
    hero_insight_text = None

# ============================================================
# HERO
# ============================================================
render_hero(
    meta_items=[
        ("Selected Period", f"{start_date:%b %d, %Y} – {end_date:%b %d, %Y}"),
        ("Tracked Days", f"{days_tracked}"),
        ("Training Sessions", f"{len(workouts)}"),
    ],
    signal_html=mdbold(hero_insight_text) if hero_insight_text else None,
    problem_sentence=(
        "Wearables generate hundreds of metrics. Athlete OS turns them into clear signals "
        "about performance trends, recovery drivers, and training load."
    ),
)

# ============================================================
# NAVIGATION
# ============================================================
tab_overview, tab_recovery, tab_training = st.tabs(["Overview", "Recovery Lab", "Training Intelligence"])

# ============================================================
# OVERVIEW
# ============================================================
with tab_overview:
    st.markdown("#### Overview")
    st.caption("How is my performance trending?")

    kpis = compute_kpis(phys, workouts, sleeps, start_date, end_date)

    # ---------- Athlete OS Intelligence ----------
    if "ai_question_count" not in st.session_state:
        st.session_state.ai_question_count = 0
    if "ai_last_result" not in st.session_state:
        st.session_state.ai_last_result = None

    with st.container(border=True, key="feature-ai-intelligence"):
        render_eyebrow("Athlete OS Intelligence")
        st.markdown("#### Ask Your Performance Data")
        st.caption(
            "AI questions send summarized Athlete OS metrics — not your raw WHOOP CSV files — "
            "to the language model for interpretation."
        )

        if not is_ai_available():
            st.info("Athlete OS Intelligence is unavailable because the AI service is not configured.")
        else:
            remaining = MAX_QUESTIONS_PER_SESSION - st.session_state.ai_question_count

            suggestions = suggested_questions(is_uploaded_mode)
            sugg_cols = st.columns(len(suggestions))
            clicked_question = None
            for col, q in zip(sugg_cols, suggestions):
                with col:
                    if st.button(q, use_container_width=True, key=f"ai_sugg_{q}"):
                        clicked_question = q

            free_text = st.text_input(
                "Ask a question about your data", key="ai_free_text",
                placeholder="e.g. What appears most associated with my recovery?",
            )
            ask_col, brief_col = st.columns([1, 1.4])
            with ask_col:
                ask_clicked = st.button("Ask", type="primary", use_container_width=True)
            with brief_col:
                brief_clicked = st.button("Generate Performance Brief", use_container_width=True)

            st.caption(f"{max(remaining, 0)} of {MAX_QUESTIONS_PER_SESSION} AI questions remaining this session.")

            question_to_ask = clicked_question or (free_text.strip() if ask_clicked and free_text.strip() else None)

            if remaining <= 0 and (question_to_ask or brief_clicked):
                st.warning(
                    f"You've reached the {MAX_QUESTIONS_PER_SESSION}-question limit for this session. "
                    "The rest of the Athlete OS dashboard keeps working normally - refresh the page to "
                    "reset the AI question limit."
                )
            elif question_to_ask:
                context = build_context(phys, workouts, sleeps, start_date, end_date, data_source, is_uploaded_mode)
                result = ask_question(question_to_ask, context)
                st.session_state.ai_question_count += 1
                st.session_state.ai_last_result = {"type": "answer", "question": question_to_ask, "result": result, "context": context}
            elif brief_clicked:
                context = build_context(phys, workouts, sleeps, start_date, end_date, data_source, is_uploaded_mode)
                result = generate_brief(context)
                st.session_state.ai_question_count += 1
                st.session_state.ai_last_result = {"type": "brief", "result": result, "context": context}

            last = st.session_state.ai_last_result
            if last:
                st.write("")
                if last["type"] == "answer":
                    result = last["result"]
                    if result["ok"]:
                        st.markdown(f'<div class="aos-signal-card">{result["answer"]}</div>', unsafe_allow_html=True)
                        if not result["deterministic_only"]:
                            with st.expander("Evidence Used"):
                                for row in recovery_evidence_rows(last["context"]):
                                    r_str = f"{row['r']:+.2f}" if row["r"] is not None else "N/A"
                                    st.markdown(
                                        f"**{row['driver']} → Recovery** — r = {r_str} · N = {row['n']} "
                                        f"· {row['strength'] or 'Insufficient data'}"
                                    )
                    elif result["error"] == "not_configured":
                        st.info("Athlete OS Intelligence is unavailable because the AI service is not configured.")
                    else:
                        st.error("Athlete OS Intelligence couldn't generate a response right now. Please try again.")
                elif last["type"] == "brief":
                    result = last["result"]
                    if result["ok"]:
                        st.markdown(f'<div class="aos-signal-card">{result["text"]}</div>', unsafe_allow_html=True)
                        with st.expander("Evidence Used"):
                            for row in recovery_evidence_rows(last["context"]):
                                r_str = f"{row['r']:+.2f}" if row["r"] is not None else "N/A"
                                st.markdown(
                                    f"**{row['driver']} → Recovery** — r = {r_str} · N = {row['n']} "
                                    f"· {row['strength'] or 'Insufficient data'}"
                                )
                        st.download_button(
                            "Download Brief (.md)",
                            data=format_brief_as_markdown(last["context"], result["text"]),
                            file_name="athlete_os_performance_brief.md",
                            mime="text/markdown",
                        )
                    elif result["error"] == "not_configured":
                        st.info("Athlete OS Intelligence is unavailable because the AI service is not configured.")
                    else:
                        st.error("Athlete OS Intelligence couldn't generate a brief right now. Please try again.")

    st.write("")

    # ---------- Observed Performance Trend (or Daily Snapshot for a single-day range) ----------
    is_single_day = start_date == end_date

    with st.container(border=True, key="feature-performance-trend"):
        if is_single_day:
            render_eyebrow("Daily Performance Snapshot")
            st.markdown(
                f'<div style="font-size:1.8rem; font-weight:800; color:var(--aos-text);">'
                f'{start_date:%b %d, %Y}</div>'
                f'<div style="color:var(--aos-muted); font-size:0.88rem; margin-top:2px;">'
                f'A summary of recovery, sleep, strain, and training recorded for this day.</div>',
                unsafe_allow_html=True,
            )
        else:
            render_eyebrow("Observed Performance Trend")
            trend_label = get_performance_trend_label(phys)
            trend_color = {
                "Improving": "var(--aos-green)", "Declining": "var(--aos-red)",
                "Mixed": "var(--aos-amber)", "Stable": "var(--aos-cyan)",
            }.get(trend_label, "var(--aos-muted)")
            st.markdown(
                f'<div style="font-size:1.8rem; font-weight:800; color:{trend_color};">{trend_label}</div>'
                f'<div style="color:var(--aos-muted); font-size:0.88rem; margin-top:2px;">'
                f'Based on the observed HRV and resting heart rate trend direction across the selected period.</div>',
                unsafe_allow_html=True,
            )
            if trend_label == "Not enough data":
                st.caption(
                    "Trend analysis requires multiple days of data. Select 7, 30, 90 days, or All Data "
                    "to explore performance trends."
                )

    st.write("")

    # ---------- Telemetry Metrics ----------
    def _trend_context(value_col, thresh, up_label="↑ TRENDING HIGHER", down_label="↓ TRENDING LOWER"):
        """Neutral trending context from the existing trend_direction calculation - no invented good/bad claim."""
        result = trend_direction(phys, "Cycle start time", value_col, "", thresh)
        if result is None:
            return "SELECTED-PERIOD AVG", "var(--aos-muted)"
        direction, _ = result
        if direction == "trended up":
            return up_label, "var(--aos-cyan)"
        elif direction == "trended down":
            return down_label, "var(--aos-cyan)"
        else:
            return "STEADY", "var(--aos-muted)"

    with st.container(border=True):
        render_eyebrow("Telemetry Metrics")
        st.markdown("#### Performance KPIs")

        row1 = st.columns(4)
        row1[0].metric("Recovery", fmt(kpis["avg_recovery"], "%"))
        recovery_band = recovery_band_label(kpis["avg_recovery"])
        row1[0].markdown(
            metric_context_html(
                recovery_band if recovery_band else "SELECTED-PERIOD AVG",
                {"GREEN RANGE": "var(--aos-green)", "YELLOW RANGE": "var(--aos-amber)", "RED RANGE": "var(--aos-red)"}
                .get(recovery_band, "var(--aos-muted)"),
            ),
            unsafe_allow_html=True,
        )

        row1[1].metric("HRV", fmt(kpis["avg_hrv"], " ms"))
        hrv_text, hrv_color = _trend_context("Heart rate variability (ms)", 1.0)
        row1[1].markdown(metric_context_html(hrv_text, hrv_color), unsafe_allow_html=True)

        row1[2].metric("Resting HR", fmt(kpis["avg_rhr"], " bpm"))
        rhr_text, rhr_color = _trend_context("Resting heart rate (bpm)", 0.5)
        row1[2].markdown(metric_context_html(rhr_text, rhr_color), unsafe_allow_html=True)

        row1[3].metric("Sleep", fmt(kpis["avg_sleep_hours"], " hrs", 1))
        row1[3].markdown(metric_context_html("SELECTED-PERIOD AVG"), unsafe_allow_html=True)

        row2 = st.columns(3)
        row2[0].metric("Day Strain", fmt(kpis["avg_day_strain"], "", 1))
        row2[0].markdown(metric_context_html("SELECTED-PERIOD AVG"), unsafe_allow_html=True)

        row2[1].metric("Sessions", kpis["total_workouts"])
        row2[1].markdown(metric_context_html("SELECTED-PERIOD TOTAL"), unsafe_allow_html=True)

        row2[2].metric("Training Rate", fmt(kpis["sessions_per_week"], " / wk", 1))
        row2[2].markdown(metric_context_html("SELECTED-PERIOD AVG"), unsafe_allow_html=True)

    st.write("")

    # ---------- Performance Story ----------
    with st.container(border=True):
        render_eyebrow("Performance Story")
        st.markdown("#### What the Data Shows")
        observations = generate_snapshot(phys, workouts, start_date, end_date)

        if observations:
            for category, text in observations:
                render_insight_card(category, mdbold(text))
        else:
            st.write("Not enough data in this range to generate observations.")

    st.write("")

    # ---------- Supporting charts ----------
    with st.container(border=True):
        render_eyebrow("Supporting Charts")
        st.markdown("#### Recovery & Cardiovascular Trends")
        st.plotly_chart(recovery_trend_chart(phys, sleeps), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(hrv_trend_chart(phys), use_container_width=True)
        with c2:
            st.plotly_chart(rhr_trend_chart(phys), use_container_width=True)

        st.markdown("###### Training Mix")
        st.plotly_chart(workout_breakdown_chart(workouts), use_container_width=True)

# ============================================================
# RECOVERY LAB
# ============================================================
with tab_recovery:
    st.markdown("#### Recovery Lab")
    st.caption("What appears to influence my recovery?")

    by_key = {d["key"]: d for d in drivers}
    valid_drivers = [d for d in drivers if not d["insufficient"]]
    insufficient_drivers = [d for d in drivers if d["insufficient"]]

    # Display order/labels for the insufficient-data panel, independent of
    # the by-strength ranking used elsewhere.
    n_display_order = [
        ("hrv", "HRV → Recovery"),
        ("rhr", "Resting HR → Recovery"),
        ("sleep", "Sleep → Recovery"),
        ("prev_strain", "Prior Strain → Following Recovery"),
    ]

    # ---------- Recovery Signals (ranked drivers, telemetry-style bars) ----------
    with st.container(border=True):
        render_eyebrow("Recovery Signals")
        st.markdown("#### Recovery Drivers")

        if not valid_drivers:
            st.markdown(
                '<div style="font-weight:700; color:var(--aos-amber); font-size:1.05rem; margin-bottom:6px;">'
                'INSUFFICIENT DATA FOR RELATIONSHIP ANALYSIS</div>'
                '<div style="color:var(--aos-muted); font-size:0.9rem; margin-bottom:14px;">'
                'Recovery relationships require at least 5 valid paired observations. This selected period '
                'does not contain enough matched recovery/physiology records.</div>',
                unsafe_allow_html=True,
            )
            st.markdown("**Valid observations:**")
            for key, label in n_display_order:
                st.markdown(f"- {label}: {by_key[key]['n']}")
            st.caption(
                "Select Last 7 Days, Last 30 Days, Last 90 Days, or All Data to explore recovery relationships."
            )
        else:
            st.caption("Ranked by strength of association with recovery in the selected period.")
            for rank, d in enumerate(valid_drivers, start=1):
                bar_pct = round(abs(d["r"]) * 100)
                bar_label = f"r = {d['r']:+.2f} · {d['strength']} ({d['direction']})"
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; margin-bottom:2px;">'
                    f'<span style="font-weight:700; color:var(--aos-text);">{rank}. {d["label"]}</span>'
                    f'<span style="color:var(--aos-muted); font-size:0.85rem;">{bar_label}</span></div>'
                    f'<div style="background:var(--aos-border); border-radius:6px; height:8px; margin-bottom:14px;">'
                    f'<div style="background:var(--aos-cyan); width:{bar_pct}%; height:8px; border-radius:6px;"></div></div>',
                    unsafe_allow_html=True,
                )

            if insufficient_drivers:
                st.markdown(
                    '<div style="color:var(--aos-muted); font-size:0.78rem; font-weight:700; '
                    'letter-spacing:.06em; text-transform:uppercase; margin-top:4px;">More data needed</div>',
                    unsafe_allow_html=True,
                )
                for d in insufficient_drivers:
                    st.markdown(
                        f'<div style="display:flex; justify-content:space-between; color:var(--aos-muted); '
                        f'font-size:0.85rem; padding:2px 0;"><span>{d["label"]}</span>'
                        f'<span>N = {d["n"]}</span></div>',
                        unsafe_allow_html=True,
                    )

    st.write("")

    # ---------- Primary Recovery Signal ----------
    with st.container(border=True, key="feature-primary-recovery-signal"):
        render_eyebrow("Primary Recovery Signal")
        st.markdown("#### Key Recovery Insight")
        if not valid_drivers:
            signal_text = "More observations are needed before a primary recovery signal can be identified."
        else:
            signal_text = mdbold(key_recovery_insight(drivers))
        st.markdown(f'<div class="aos-signal-card">{signal_text}</div>', unsafe_allow_html=True)

    st.write("")

    def render_driver_card(d):
        st.markdown(f"##### {d['label']}")
        if d["insufficient"]:
            st.caption(f"Sample size: N = {d['n']}")
            st.info("Not enough data to calculate a reliable relationship for this period.")
            return
        st.caption(f"Correlation: r = {d['r']:+.2f}  •  Sample size: N = {d['n']}")
        st.plotly_chart(
            driver_scatter_chart(d["chart_df"], d["axis_x"], d["axis_y"], d["label"], COLOR_BLUE),
            use_container_width=True,
        )
        st.caption(d["interpretation"])

    # ---------- Supporting Relationships ----------
    with st.container(border=True):
        render_eyebrow("Supporting Relationships")
        st.markdown("#### Recovery Drivers in Detail")

        top_row = st.columns(2)
        with top_row[0]:
            render_driver_card(by_key["prev_strain"])
        with top_row[1]:
            render_driver_card(by_key["sleep"])

        bottom_row = st.columns(2)
        with bottom_row[0]:
            render_driver_card(by_key["hrv"])
        with bottom_row[1]:
            render_driver_card(by_key["rhr"])

    st.write("")

    with st.expander("How this analysis works"):
        st.markdown(
            "- Correlations are calculated from the WHOOP data in your currently selected date range.\n"
            "- Missing values are excluded pairwise for each relationship, independently.\n"
            "- Previous-day strain is taken only from **completed** cycles and aligned to the "
            "**following** cycle's recovery score, not the same-day value.\n"
            "- Correlation coefficients describe **association, not causation**.\n"
            "- This is exploratory fitness-data analysis, not medical advice."
        )

# ============================================================
# TRAINING INTELLIGENCE
# ============================================================
with tab_training:
    st.markdown("#### Training Intelligence")
    st.caption("How does each type of training load my body?")

    all_activity_types = sorted(workouts["Activity name"].unique()) if not workouts.empty else []
    st.caption(
        f"{len(workouts)} workouts • {len(all_activity_types)} activity types in the selected period."
    )

    if workouts.empty:
        st.info("No workouts available in the selected date range. Try widening the range in the sidebar.")
    else:
        full_profile = compute_activity_profile(workouts)

        activity_options = ["All Activities"] + all_activity_types
        selected_activity = st.selectbox("Activity", activity_options)

        workouts_selected = (
            workouts if selected_activity == "All Activities"
            else workouts[workouts["Activity name"] == selected_activity]
        )

        with st.container(border=True):
            render_eyebrow("Snapshot")
            st.markdown(f"#### {selected_activity} KPIs")
            tk = compute_training_kpis(workouts_selected)

            row1 = st.columns(3)
            row1[0].metric("Total Sessions", tk["total_sessions"])
            row1[1].metric("Average Strain", fmt(tk["avg_strain"], "", 1))
            row1[2].metric("Average Duration", fmt(tk["avg_duration"], " min"))

            row2 = st.columns(3)
            row2[0].metric("Average Calories", fmt(tk["avg_calories"], " kcal"))
            row2[1].metric("Average Heart Rate", fmt(tk["avg_hr"], " bpm"))
            row2[2].metric("Average Max Heart Rate", fmt(tk["avg_max_hr"], " bpm"))

        st.write("")

        profile_col_map = {
            "activity": "Activity", "sessions": "Sessions", "avg_strain": "Avg Strain",
            "avg_duration": "Avg Duration", "avg_calories": "Avg Calories",
            "avg_hr": "Avg HR", "avg_max_hr": "Avg Max HR",
        }
        profile_style = {
            "Sessions": "{:.0f}",
            "Avg Strain": lambda v: f"{v:.1f}" if pd.notna(v) else "N/A",
            "Avg Duration": lambda v: f"{v:.0f} min" if pd.notna(v) else "N/A",
            "Avg Calories": lambda v: f"{v:.0f} kcal" if pd.notna(v) else "N/A",
            "Avg HR": lambda v: f"{v:.0f} bpm" if pd.notna(v) else "N/A",
            "Avg Max HR": lambda v: f"{v:.0f} bpm" if pd.notna(v) else "N/A",
        }

        # ---------- SIGNATURE: Cricket vs Gym (Demo) / Your Training Comparison (uploaded) ----------
        if is_uploaded_mode:
            section_title = "Your Training Comparison"
            cvg_activities = pick_top_activities(full_profile, max_n=3)
            anchor_activity = cvg_activities[0] if cvg_activities else None
            missing_note = None
        else:
            section_title = "Cricket vs Gym Training"
            cvg_activities = ["Cricket", "Functional Fitness", "Strength Trainer"]
            anchor_activity = "Cricket"
            missing_note = [a for a in cvg_activities if a not in full_profile["activity"].values]

        render_eyebrow("Signature Comparison")
        with st.container(border=True, key="feature-cricket-vs-gym"):
            st.markdown(f"#### {section_title}")
            cvg_profile = filter_profile(full_profile, cvg_activities)

            if missing_note:
                st.caption(f"Limited comparison: no data for {', '.join(missing_note)} in this period.")

            if cvg_profile.empty:
                st.info("Not enough activity data in this period for a training comparison.")
            else:
                leaders = identify_cvg_leaders(cvg_profile)
                stat_fields = [
                    ("avg_strain", "Avg Strain", "", 1),
                    ("avg_duration", "Avg Duration", " min", 0),
                    ("avg_calories", "Avg Calories", " kcal", 0),
                    ("avg_hr", "Avg HR", " bpm", 0),
                ]

                card_cols = st.columns(len(cvg_profile))
                for col, (_, row) in zip(card_cols, cvg_profile.iterrows()):
                    with col:
                        with st.container(border=True):
                            st.markdown(f"**{row['activity']}**")
                            n_note = f" · {small_sample_label(row['sessions'])}" if row["sessions"] <= MIN_SAMPLE_SIZE else ""
                            st.caption(f"{int(row['sessions'])} sessions{n_note}")
                            for key, label, unit, decimals in stat_fields:
                                val = row[key]
                                val_str = "N/A" if pd.isna(val) else f"{val:.{decimals}f}{unit}"
                                is_leader = leaders.get(key) == row["activity"]
                                css_class = "aos-stat-row win" if is_leader else "aos-stat-row"
                                st.markdown(
                                    f'<div class="{css_class}"><span class="label">{label}</span>'
                                    f'<span class="value">{val_str}</span></div>',
                                    unsafe_allow_html=True,
                                )

                st.write("")
                render_eyebrow("What the Data Says")
                cvg_insights = (
                    generate_anchor_comparison_insights(cvg_profile, anchor=anchor_activity)
                    if anchor_activity else []
                )
                if cvg_insights:
                    for insight in cvg_insights:
                        render_insight_card("Comparison", mdbold(insight))
                else:
                    st.write("Not enough overlapping data among these activities to generate comparisons.")

        st.write("")

        with st.container(border=True):
            render_eyebrow("Training Profile")
            st.markdown("#### Workout Profile Comparison")

            display_profile = full_profile.rename(columns=profile_col_map).set_index("Activity")
            st.dataframe(display_profile.style.format(profile_style), use_container_width=True)
            st.caption("Duration averages exclude tracking-error outliers (sessions still count toward Sessions).")

            small_sample_activities = [
                f"{row['activity']} ({small_sample_label(row['sessions'])})"
                for _, row in full_profile.iterrows() if row["sessions"] <= MIN_SAMPLE_SIZE
            ]
            if small_sample_activities:
                st.caption(f"⚠ {' • '.join(small_sample_activities)} — interpret with caution.")

        st.write("")

        with st.container(border=True):
            render_eyebrow("Intensity")
            st.markdown("#### Intensity Profile")
            st.caption(f"Which workouts produce the greatest physiological intensity? "
                       f"Bars in grey reflect {MIN_SAMPLE_SIZE} or fewer sessions.")
            st.plotly_chart(intensity_profile_chart(full_profile, MIN_SAMPLE_SIZE), use_container_width=True)

        st.write("")

        with st.container(border=True):
            render_eyebrow("Cardio Load")
            st.markdown("#### Heart Rate Zone Profile")
            zone_profile = compute_hr_zone_profile(workouts)
            if zone_profile.empty:
                st.info("Not enough valid heart-rate-zone records in this period to build a zone profile "
                         "(each activity needs at least 3 sessions with zone data).")
            else:
                st.caption("Average % of workout time spent in each HR zone, by activity.")
                st.plotly_chart(hr_zone_stacked_chart(zone_profile), use_container_width=True)

        st.write("")

        with st.container(border=True):
            render_eyebrow("Training Volume")
            st.markdown("#### Training Volume Over Time")
            weekly = compute_weekly_training_volume(workouts_selected)

            vol_col1, vol_col2 = st.columns(2)
            with vol_col1:
                st.plotly_chart(weekly_sessions_chart(weekly), use_container_width=True)
            with vol_col2:
                st.plotly_chart(weekly_strain_chart(weekly), use_container_width=True)

        st.write("")

        with st.container(border=True):
            render_eyebrow("Training Signals")
            st.markdown("#### Training Intelligence Summary")
            summary = training_summary(full_profile)

            if not summary:
                st.write("Not enough data in this range to generate a summary.")
            else:
                s1, s2, s3, s4, s5 = st.columns(5)
                mf = summary.get("most_frequent")
                if mf:
                    s1.metric("Most Frequent", mf["activity"], f"{mf['value']:.0f} sessions")
                hs = summary.get("highest_strain")
                if hs:
                    s2.metric("Highest Strain", hs["activity"], f"{hs['value']:.1f} avg strain")
                ld = summary.get("longest_duration")
                if ld:
                    s3.metric("Longest Avg Session", ld["activity"], f"{ld['value']:.0f} min")
                hc = summary.get("highest_calories")
                if hc:
                    s4.metric("Highest Avg Calories", hc["activity"], f"{hc['value']:.0f} kcal")
                hh = summary.get("highest_hr")
                if hh:
                    s5.metric("Highest Avg HR", hh["activity"], f"{hh['value']:.0f} bpm")

                small_sample_flags = [e["activity"] for e in summary.values() if e and e["sessions"] <= MIN_SAMPLE_SIZE]
                if small_sample_flags:
                    st.caption(
                        f"⚠ {', '.join(sorted(set(small_sample_flags)))} appear above with {MIN_SAMPLE_SIZE} or "
                        f"fewer sessions in this period — treat as a small-sample result."
                    )

# ============================================================
# DATA & METHODOLOGY (shown once, describes the full dataset; collapsed by default)
# ============================================================
st.write("")
with st.expander("DATA & METHODOLOGY", expanded=False):
    st.markdown(
        "Athlete OS analyzes historical WHOOP CSV data using Python, Pandas, Streamlit, and Plotly."
    )
    st.markdown(
        f"- **Dataset range:** {min_date:%b %d, %Y} — {max_date:%b %d, %Y}\n"
        f"- **Physiological cycles analyzed:** {len(phys_all)}\n"
        f"- **Workout records:** {len(workouts_all)}\n"
        f"- **Sleep records:** {len(sleeps_all)}\n"
        f"- **Workout types:** {workouts_all['Activity name'].nunique()}"
    )
    st.markdown(
        "- Naps are separated from main sleep and excluded from sleep-duration metrics.\n"
        "- Incomplete/open WHOOP cycles are handled carefully: recovery/HRV/RHR readings from an "
        "open cycle are still used, but its Day Strain is excluded until the cycle closes.\n"
        "- The known workout duration-tracking outlier is excluded only from duration averages — "
        "it still counts as a session everywhere else.\n"
        "- Correlations throughout this app describe **association, not causation**.\n"
        "- This is fitness/performance data exploration, not medical advice."
    )
