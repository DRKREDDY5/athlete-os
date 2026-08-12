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
    filter_by_date, get_overall_date_bounds,
)
from src.metrics import compute_kpis, generate_snapshot
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
    identify_cvg_leaders,
)
from src.theme import inject_theme, mdbold, render_insight_card, render_eyebrow

st.set_page_config(page_title="Athlete OS", page_icon="📊", layout="wide")
inject_theme()

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
    render_eyebrow("Athlete OS")
    st.markdown("#### Date Range")

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

# Computed once, shared by the hero's Key Insight and the Recovery Lab tab.
drivers = compute_recovery_drivers(phys, sleeps)
hero_insight_text = key_recovery_insight(drivers)
if hero_insight_text.startswith("Not enough data"):
    hero_insight_text = None

# ============================================================
# HERO
# ============================================================
render_eyebrow("Performance Intelligence")
st.markdown(
    '<h1 style="margin-top:0; margin-bottom:2px;">Athlete OS</h1>'
    '<div style="font-size:1.05rem; color:var(--aos-muted); margin-bottom:14px;">'
    'Performance Intelligence for Training, Recovery &amp; Sleep</div>',
    unsafe_allow_html=True,
)

meta_cols = st.columns(4)
meta_items = [
    ("Selected Period", f"{start_date:%b %d, %Y} – {end_date:%b %d, %Y}"),
    ("Tracked Days", f"{days_tracked}"),
    ("Workouts", f"{len(workouts)}"),
    ("Data Source", "WHOOP Export"),
]
for col, (label, value) in zip(meta_cols, meta_items):
    col.markdown(
        f'<div class="aos-eyebrow">{label}</div><div style="font-size:1rem; font-weight:600;">{value}</div>',
        unsafe_allow_html=True,
    )

if hero_insight_text:
    st.markdown(
        f'<div class="aos-hero-insight"><div class="aos-eyebrow">Key Insight</div>{mdbold(hero_insight_text)}</div>',
        unsafe_allow_html=True,
    )

st.write("")

# ============================================================
# NAVIGATION
# ============================================================
tab_overview, tab_recovery, tab_training = st.tabs(["Overview", "Recovery Lab", "Training Intelligence"])

# ============================================================
# OVERVIEW
# ============================================================
with tab_overview:
    with st.container(border=True):
        render_eyebrow("Snapshot")
        st.markdown("#### Performance KPIs")
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

    st.write("")

    with st.container(border=True):
        render_eyebrow("Trends")
        st.markdown("#### Recovery & Cardiovascular Trends")
        st.plotly_chart(recovery_trend_chart(phys, sleeps), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(hrv_trend_chart(phys), use_container_width=True)
        with c2:
            st.plotly_chart(rhr_trend_chart(phys), use_container_width=True)

        st.plotly_chart(workout_breakdown_chart(workouts), use_container_width=True)

    st.write("")

    with st.container(border=True):
        render_eyebrow("Insights")
        st.markdown("#### Athlete Intelligence")
        observations = generate_snapshot(phys, workouts, start_date, end_date)

        if observations:
            for category, text in observations:
                render_insight_card(category, mdbold(text))
        else:
            st.write("Not enough data in this range to generate observations.")

# ============================================================
# RECOVERY LAB
# ============================================================
with tab_recovery:
    st.caption("Explore how training load, sleep, HRV, and resting heart rate relate to recovery.")

    by_key = {d["key"]: d for d in drivers}

    with st.container(border=True):
        render_eyebrow("Ranked")
        st.markdown("#### Recovery Drivers")
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

    st.write("")

    with st.container(border=True):
        render_eyebrow("Headline")
        st.markdown("#### Key Recovery Insight")
        st.markdown(
            f'<div class="aos-hero-insight">{mdbold(key_recovery_insight(drivers))}</div>',
            unsafe_allow_html=True,
        )

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

    with st.container(border=True):
        render_eyebrow("Relationships")
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
    all_activity_types = sorted(workouts["Activity name"].unique()) if not workouts.empty else []
    st.caption(
        f"Compare training load, intensity, duration, and cardiovascular demand across workout types. "
        f"{len(workouts)} workouts • {len(all_activity_types)} activity types."
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

        with st.container(border=True):
            render_eyebrow("Comparison")
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
            render_eyebrow("Volume")
            st.markdown("#### Training Volume Over Time")
            weekly = compute_weekly_training_volume(workouts_selected)

            vol_col1, vol_col2 = st.columns(2)
            with vol_col1:
                st.plotly_chart(weekly_sessions_chart(weekly), use_container_width=True)
            with vol_col2:
                st.plotly_chart(weekly_strain_chart(weekly), use_container_width=True)

        st.write("")

        # ---------- SIGNATURE: Cricket vs Gym ----------
        render_eyebrow("Signature Comparison")
        with st.container(border=True):
            st.markdown("#### Cricket vs Gym Training")
            cvg_activities = ["Cricket", "Functional Fitness", "Strength Trainer"]
            cvg_profile = filter_profile(full_profile, cvg_activities)

            missing = [a for a in cvg_activities if a not in cvg_profile["activity"].values]
            if missing:
                st.caption(f"Limited comparison: no data for {', '.join(missing)} in this period.")

            if cvg_profile.empty:
                st.info("None of Cricket, Functional Fitness, or Strength Trainer have data in this period.")
            else:
                leaders = identify_cvg_leaders(cvg_profile)
                stat_fields = [
                    ("avg_strain", "Avg Strain", "", 1),
                    ("avg_duration", "Avg Duration", " min", 0),
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
                cvg_display = cvg_profile.rename(columns=profile_col_map).set_index("Activity")
                st.dataframe(cvg_display.style.format(profile_style), use_container_width=True)

                cvg_insights = generate_anchor_comparison_insights(cvg_profile, anchor="Cricket")
                if cvg_insights:
                    for insight in cvg_insights:
                        render_insight_card("Comparison", mdbold(insight))
                else:
                    st.write("Not enough overlapping data among these activities to generate comparisons.")

        st.write("")

        with st.container(border=True):
            render_eyebrow("Summary")
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
# ABOUT THIS ANALYSIS (shown once, describes the full dataset)
# ============================================================
st.write("")
with st.expander("About This Analysis"):
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
