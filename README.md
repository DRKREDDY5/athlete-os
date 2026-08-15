# Athlete OS

## Personal Performance Intelligence

**Live App:** https://athlete-os-rushikeshava.streamlit.app/
**GitHub:** https://github.com/DRKREDDY5/athlete-os

### Problem

Wearable platforms like WHOOP produce rich raw data — recovery, HRV, resting heart rate,
sleep stages, workout strain — but the export is a pile of CSV files. It's hard to see, in
one place, how training load, sleep, and recovery actually relate to each other over time.

### Solution

Athlete OS turns raw WHOOP CSV exports into an interactive Streamlit performance console. It
applies consistent data-cleaning rules (open-cycle handling, nap separation, duration-outlier
exclusion), then surfaces three focused views — an Overview / Performance Command Center, a
correlation lab for recovery drivers, and a training comparison tool — plus an AI layer that
interprets (never calculates) those same deterministic results in plain language.

It works two ways:

- **Demo Athlete** — explore the built-in dataset (the original author's ~7 months of WHOOP data).
- **Analyze My WHOOP Data** — upload your own WHOOP export and get the exact same analysis,
  scoped to your session only.

### Features

- **Overview / Performance Command Center** — observed performance trend, telemetry KPI
  cards, deterministic "Performance Story" insights, and supporting recovery/training charts
- **Recovery Lab** — correlates recovery against previous-cycle strain, sleep duration, HRV,
  and resting heart rate; ranks the relationships by strength and states the strongest one,
  with an explicit insufficient-data state when a selected range doesn't have enough paired
  observations
- **Training Intelligence** — compares workout types on strain, duration, calories, and
  heart-rate zones, with a **dynamic training comparison** (Demo Athlete's fixed "Cricket vs
  Gym" story, or an automatically chosen top-3-by-session-count comparison for uploaded data —
  never assumes an uploaded athlete has any specific activity)
- **Athlete OS Intelligence** — ask natural-language questions about the active dataset/date
  range ("What drives my recovery?", "Compare my top activities"), with a grounded **Evidence
  Used** panel and a downloadable **Performance Brief** (see [Architecture](#architecture))
- **Analyze My WHOOP Data** — upload your three WHOOP export CSVs in any order; Athlete OS
  identifies which file is which by **schema, not filename** (see [Data Ingestion](#data-ingestion))
- Global date filtering (Last 7/30/90 days, All Data, custom range, single-day snapshot mode)
- Automatic, dynamically calculated (non-hard-coded) insights throughout

### Architecture

```
WHOOP Data (Demo dataset or your upload)
        ↓
Validation & Cleaning  (schema check, open-cycle/outlier/nap handling)
        ↓
Deterministic Pandas Analytics  (KPIs, correlations, activity profiles — all in src/)
        ↓
Charts & Insights  (Plotly charts, rule-based deterministic text insights)
        ↓
AI Interpretation  (Athlete OS Intelligence, optional, on explicit user request)
```

**The core metrics are always calculated deterministically by Pandas** — recovery averages,
correlations, sample sizes, activity comparisons, HR zones, everything shown on the Overview,
Recovery Lab, and Training Intelligence pages. **The LLM does not calculate any of these
numbers.** When you use Athlete OS Intelligence, the already-computed results are packaged
into a compact summary and handed to the model purely to *explain* them in natural language;
the "Evidence Used" figures shown under an AI answer are read directly from that same
deterministic output, not parsed out of the model's reply.

### Data Ingestion

Uploaded files are read straight from Streamlit's in-memory upload buffer and classified by
comparing their columns against the schema each of the three WHOOP export types requires —
independent of what the file is named or what order you upload them in. If two files both
look like the same export type, or a file doesn't match any known WHOOP export schema,
Athlete OS reports that clearly instead of guessing.

### Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- Groq (LLM inference for Athlete OS Intelligence)
- Claude in VS Code for vibe coding

### How to Run

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Demo Athlete mode works out of the box if you have the three original WHOOP CSVs locally, or
via Streamlit Secrets in a cloud deployment (see [Privacy](#privacy)). Analyze My WHOOP Data
mode works immediately with no setup — just upload your own export. Athlete OS Intelligence
is optional: without a `GROQ_API_KEY`, the rest of the app works normally and that section
simply reports itself unavailable.

### Project Structure

```
app.py                        Streamlit entry point — page layout, sidebar, data source, AI section
analyze.py                    Standalone exploratory-analysis script (initial EDA, not imported by the app)
requirements.txt              Python dependencies
src/
  data_loader.py              Demo Athlete loading + shared clean_* functions used by both data sources
  uploads.py                  Schema-based validation & classification for uploaded WHOOP exports
  metrics.py                  Overview KPIs and deterministic "Performance Story" insights
  analysis.py                 Recovery Lab: correlation helper and driver-relationship builders
  training.py                 Training Intelligence: activity profiles, HR-zone stats, comparisons
  charts.py                   All Plotly chart builders
  theme.py                    Dark "performance console" visual design system
  ai_intelligence.py          Athlete OS Intelligence: context building, Groq calls, evidence, briefs
.streamlit/config.toml        Streamlit theme configuration
physiological_cycles.csv      Demo Athlete raw WHOOP export (gitignored, not included)
workouts.csv                  Demo Athlete raw WHOOP export (gitignored, not included)
sleeps.csv                    Demo Athlete raw WHOOP export (gitignored, not included)
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
  is reported as **association, not causation**, by both the deterministic insight text and
  Athlete OS Intelligence.

### Privacy

- The Demo Athlete's raw WHOOP CSV files (`physiological_cycles.csv`, `workouts.csv`,
  `sleeps.csv`) are excluded from this GitHub repository via `.gitignore`, along with logs,
  `.streamlit/secrets.toml`, `__pycache__/`, and local virtual environments. They are not in
  GitHub; the deployed app reads them from that deployment's own Streamlit Secrets instead.
- **Uploaded WHOOP data (Analyze My WHOOP Data) is not written to disk, not added to any
  database, and not committed to this repository.** It's read directly from the upload
  buffer and processed for the current session only.
- When you explicitly use an Athlete OS Intelligence feature (asking a question or
  generating a brief), Athlete OS intentionally sends Groq a compact summary of
  already-computed metrics for your selected view — not your raw WHOOP CSV rows. This is a
  description of what the application code does, not a security guarantee about Groq's own
  infrastructure or a claim of complete data protection.

### Week 1 — Gen Academy

This project was created for the **Week 1: "Data Analysis with Vibe Coding"** project in the
**Mastering Agentic AI Bootcamp** at **The Gen Academy**.
