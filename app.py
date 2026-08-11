"""
Athlete OS - Personal Performance Intelligence Dashboard
Iteration 3: Overview + Recovery Driver Lab.

Run with: streamlit run app.py
"""

import datetime as dt

import streamlit as st

from src.data_loader import (
    load_physiological_cycles, load_workouts, load_sleeps,
    filter_by_date, get_overall_date_bounds,
)
from src.metrics import compute_kpis, generate_snapshot
from src.charts import (
    recovery_trend_chart, hrv_trend_chart, rhr_trend_chart, workout_breakdown_chart,
    driver_scatter_chart,
)
from src.analysis import compute_recovery_drivers, key_recovery_insight

st.set_page_config(page_title="Athlete OS", page_icon="📊", layout="wide")

# ---------- Load & clean data (cached) ----------
phys_all = load_physiological_cycles()
workouts_all = load_workouts()
sleeps_all = load_sleeps()
min_date, max_date = get_overall_date_bounds(phys_all, workouts_all, sleeps_all)

# ---------- Sidebar: date range controls ----------
if "start_date" not in st.session_state:
    st.session_state.start_date = min_date
    st.session_state.end_date = max_date


def _set_range(days: int | None):
    st.session_state.active_quick_range = days
    st.session_state.end_date = max_date
    st.session_state.start_date = max_date if days is None else max(min_date, max_date - dt.timedelta(days=days - 1))
    if days is None:
        st.session_state.start_date = min_date


if "active_quick_range" not in st.session_state:
    st.session_state.active_quick_range = None  # "All data" by default


def _on_manual_date_change():
    # Manual date-input edits deactivate the quick-range highlight.
    st.session_state.active_quick_range = "custom"


with st.sidebar:
    st.header("Athlete OS")
    page = st.radio("Page", ["Overview", "Recovery Lab"], label_visibility="collapsed")
    st.divider()
    st.header("Date Range")

    quick_ranges = [("Last 7 days", 7), ("Last 30 days", 30), ("Last 90 days", 90), ("All data", None)]
    col1, col2 = st.columns(2)
    for i, (label, days) in enumerate(quick_ranges):
        target_col = col1 if i % 2 == 0 else col2
        is_active = st.session_state.active_quick_range == days
        with target_col:
            if st.button(("● " if is_active else "") + label, use_container_width=True,
                         type="primary" if is_active else "secondary"):
                _set_range(days)

    st.date_input("Start date", key="start_date", min_value=min_date, max_value=max_date, on_change=_on_manual_date_change)
    st.date_input("End date", key="end_date", min_value=min_date, max_value=max_date, on_change=_on_manual_date_change)

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

# ============================================================
# OVERVIEW
# ============================================================
if page == "Overview":
    st.title("Athlete OS")
    st.caption("Personal Performance Intelligence Dashboard")

    st.markdown(
        f"**Selected Period:** {start_date:%b %d, %Y} — {end_date:%b %d, %Y}  \n"
        f"{days_tracked} tracked days • {len(workouts)} workouts"
    )
    st.divider()

    # ---------- KPI cards ----------
    kpis = compute_kpis(phys, workouts, sleeps, start_date, end_date)

    row1 = st.columns(4)
    row1[0].metric("Average Recovery", fmt(kpis["avg_recovery"], "%"))
    row1[1].metric("Average HRV", fmt(kpis["avg_hrv"], " ms"))
    row1[2].metric("Resting Heart Rate", fmt(kpis["avg_rhr"], " bpm"))
    row1[3].metric("Average Sleep", fmt(kpis["avg_sleep_hours"], " hrs", 1))

    row2 = st.columns(3)
    row2[0].metric("Days Tracked", kpis["days_tracked"])
    row2[1].metric("Total Workouts", kpis["total_workouts"])
    row2[2].metric("Average Day Strain", fmt(kpis["avg_day_strain"], "", 1))

    st.divider()

    # ---------- Charts ----------
    st.plotly_chart(recovery_trend_chart(phys, sleeps), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(hrv_trend_chart(phys), use_container_width=True)
    with c2:
        st.plotly_chart(rhr_trend_chart(phys), use_container_width=True)

    st.plotly_chart(workout_breakdown_chart(workouts), use_container_width=True)

    st.divider()

    # ---------- Athlete Intelligence ----------
    st.subheader("Athlete Intelligence")
    observations = generate_snapshot(phys, workouts, start_date, end_date)

    if observations:
        for category, text in observations:
            st.markdown(f"**{category}** — {text}")
    else:
        st.write("Not enough data in this range to generate observations.")

# ============================================================
# RECOVERY LAB
# ============================================================
else:
    st.title("Recovery Driver Lab")
    st.caption("Explore how training load, sleep, HRV, and resting heart rate relate to recovery.")

    valid_recovery_n = phys["Recovery score %"].notna().sum()
    st.markdown(
        f"**Selected Period:** {start_date:%b %d, %Y} — {end_date:%b %d, %Y}  \n"
        f"{valid_recovery_n} valid recovery observations"
    )
    st.divider()

    drivers = compute_recovery_drivers(phys, sleeps)
    by_key = {d["key"]: d for d in drivers}

    # ---------- Recovery Drivers scoreboard ----------
    st.subheader("Recovery Drivers")
    st.caption("Ranked by strength of association with recovery in the selected period.")

    for rank, d in enumerate(drivers, start=1):
        cols = st.columns([0.5, 2.5, 1.3, 1.5])
        cols[0].markdown(f"**{rank}**")
        cols[1].markdown(f"**{d['label']}**")
        if d["insufficient"]:
            cols[2].markdown("N/A")
            cols[3].markdown("Not enough data")
        else:
            cols[2].markdown(f"r = {d['r']:+.2f}")
            cols[3].markdown(f"{d['strength']} ({d['direction']})")

    st.divider()

    # ---------- Key Recovery Insight ----------
    st.subheader("Key Recovery Insight")
    st.markdown(key_recovery_insight(drivers))
    st.divider()

    # ---------- 2x2 driver detail charts ----------
    def render_driver_card(d):
        st.markdown(f"##### {d['label']}")
        if d["insufficient"]:
            st.caption(f"Sample size: N = {d['n']}")
            st.info("Not enough data to calculate a reliable relationship for this period.")
            return
        st.caption(f"Correlation: r = {d['r']:+.2f}  •  Sample size: N = {d['n']}")
        st.plotly_chart(
            driver_scatter_chart(d["chart_df"], d["axis_x"], d["axis_y"], d["label"], "#2a78d6"),
            use_container_width=True,
        )
        st.caption(d["interpretation"])

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

    st.divider()

    # ---------- Methodology note ----------
    with st.expander("How this analysis works"):
        st.markdown(
            "- Correlations are calculated from the WHOOP data in your currently selected date range.\n"
            "- Missing values are excluded pairwise for each relationship, independently.\n"
            "- Previous-day strain is taken only from **completed** cycles and aligned to the "
            "**following** cycle's recovery score, not the same-day value.\n"
            "- Correlation coefficients describe **association, not causation**.\n"
            "- This is exploratory fitness-data analysis, not medical advice."
        )
