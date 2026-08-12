# Athlete OS

## Personal Performance Intelligence Dashboard

### Problem

Wearable platforms like WHOOP produce rich raw data — recovery, HRV, resting heart rate,
sleep stages, workout strain — but the export is a pile of CSV files. It's hard to see, in
one place, how training load, sleep, and recovery actually relate to each other over time.

### Solution

Athlete OS turns raw WHOOP CSV exports into an interactive Streamlit dashboard. It applies
consistent data-cleaning rules (open-cycle handling, nap separation, duration-outlier
exclusion), then surfaces three focused views: a daily performance overview, a correlation
lab for recovery drivers, and a workout-type comparison tool — all driven by global date and
activity filters, all computed live from whatever data is loaded.

### Features

- **Athlete Overview** — KPI summary, recovery/HRV/resting-HR trends, workout frequency,
  and deterministic "Athlete Intelligence" insights
- **Recovery Driver Lab** — correlates recovery against previous-day strain, sleep duration,
  HRV, and resting heart rate, ranks the relationships, and states the strongest one
- **Training Intelligence** — compares workout types on strain, duration, calories, and
  heart-rate zones, including a dedicated Cricket vs. Gym comparison
- Global date filtering (Last 7/30/90 days, All Data, custom range)
- Activity-type filtering on Training Intelligence
- Automatic, dynamically calculated (non-hard-coded) insights throughout

### Dataset

The original project was built using approximately seven months of personal WHOOP export
data (physiological cycles, workouts, and sleep records).

**Personal/raw data is intentionally excluded from the public repository for privacy** — see
[Privacy](#privacy) below. To run the app yourself, supply your own WHOOP CSV exports
(`physiological_cycles.csv`, `workouts.csv`, `sleeps.csv`) in the project root.

### Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- Claude in VS Code for vibe coding

### How to Run

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

### Project Structure

```
app.py                        Streamlit entry point — page layout, sidebar, filters
analyze.py                    Standalone exploratory-analysis script (initial EDA, not imported by the app)
requirements.txt              Python dependencies
src/
  data_loader.py              Reads & cleans the WHOOP CSVs (cached), open-cycle/outlier/nap flags
  metrics.py                  Overview KPIs and deterministic "Athlete Intelligence" insights
  analysis.py                 Recovery Lab: correlation helper and driver-relationship builders
  training.py                 Training Intelligence: activity profiles, HR-zone stats, comparisons
  charts.py                   All Plotly chart builders
physiological_cycles.csv      Raw WHOOP export (gitignored, not included)
workouts.csv                  Raw WHOOP export (gitignored, not included)
sleeps.csv                    Raw WHOOP export (gitignored, not included)
```

### Data Analysis Notes

- **Duration outliers:** a known ~746-minute tracking-error workout still counts as a
  session everywhere (totals, frequency counts) but is excluded from duration averages via
  a `duration_is_outlier` flag.
- **Nap separation:** naps are flagged separately from main sleep and excluded from
  sleep-duration metrics, so a short nap can't dilute the "how well did I sleep" numbers.
- **Incomplete cycles:** the current in-progress WHOOP cycle (`Cycle end time` missing) has
  its Day Strain excluded from strain averages, since strain isn't final until the cycle
  closes — but its Recovery/HRV/RHR readings (captured at wake-up) are still used.
- **Correlation methodology:** all Recovery Lab relationships use pairwise NaN exclusion,
  require at least 5 valid observations, and guard against zero-variance series. Previous-day
  strain is aligned to the *following* cycle's recovery score (not same-day), and only when
  the two cycles are genuinely consecutive (no tracking gap between them). Every correlation
  is reported as **association, not causation**.

### Privacy

Personal WHOOP CSV files (`physiological_cycles.csv`, `workouts.csv`, `sleeps.csv`) are
excluded from version control via `.gitignore`, along with logs, `__pycache__/`, and local
virtual environments. No personal health data is committed to this repository.

### Week 1 — Gen Academy

This project was created for the **Week 1: "Data Analysis with Vibe Coding"** project in the
**Mastering Agentic AI Bootcamp** at **The Gen Academy**.
