"""
Visual design system for Athlete OS.

A single CSS injection (inject_theme) plus a couple of small HTML-rendering
helpers used throughout app.py to give KPI cards, section containers, and
insight text a consistent "performance product" look. No analysis logic
lives here - this module is presentation only.
"""

import re

import streamlit as st

THEME_CSS = """
<style>
:root {
    --aos-navy: #0b1220;
    --aos-blue: #2a78d6;
    --aos-blue-dark: #163f73;
    --aos-bg: #f5f6f8;
    --aos-card: #ffffff;
    --aos-border: #e3e5ea;
    --aos-text: #10131a;
    --aos-muted: #6b7280;
}

.stApp { background: var(--aos-bg); }

/* KPI metric cards */
div[data-testid="stMetric"] {
    background: var(--aos-card);
    border: 1px solid var(--aos-border);
    border-radius: 12px;
    padding: 14px 18px 10px 18px;
    box-shadow: 0 1px 2px rgba(16,19,26,0.05);
}
div[data-testid="stMetricLabel"] {
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: .02em;
    color: var(--aos-muted);
    text-transform: uppercase;
}
div[data-testid="stMetricValue"] {
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--aos-text);
}

/* Bordered containers used as dashboard-module cards */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border-color: var(--aos-border) !important;
}

h1 { font-weight: 800; letter-spacing: -0.02em; color: var(--aos-navy); }
h2, h3, h4 { font-weight: 700; color: var(--aos-navy); }

/* Tabs as a segmented product nav */
button[data-baseweb="tab"] { font-weight: 600; font-size: 0.95rem; }
div[data-baseweb="tab-highlight"] { background-color: var(--aos-blue) !important; height: 3px !important; }

/* Pill-shaped buttons (sidebar quick-range) */
.stButton > button { border-radius: 999px; font-weight: 600; }

/* Small uppercase section label ("eyebrow") */
.aos-eyebrow {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--aos-blue);
    margin-bottom: 2px;
}

/* Insight cards (Athlete Intelligence, Cricket vs Gym observations, ...) */
.aos-insight {
    background: var(--aos-card);
    border: 1px solid var(--aos-border);
    border-left: 4px solid var(--aos-blue);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.93rem;
    line-height: 1.4;
}
.aos-insight b { color: var(--aos-navy); }
.aos-insight-category {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: var(--aos-blue);
    margin-right: 8px;
}

/* Hero "Key Insight" callout */
.aos-hero-insight {
    background: linear-gradient(135deg, var(--aos-navy), var(--aos-blue-dark));
    color: #ffffff;
    border-radius: 14px;
    padding: 16px 20px;
    margin: 8px 0 4px 0;
    font-size: 0.98rem;
    line-height: 1.45;
}
.aos-hero-insight .aos-eyebrow { color: #9cc4f2; }
.aos-hero-insight b { color: #ffffff; }

/* Compact stat rows inside Cricket vs Gym cards */
.aos-stat-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.86rem;
    border-bottom: 1px solid var(--aos-border);
}
.aos-stat-row:last-child { border-bottom: none; }
.aos-stat-row .label { color: var(--aos-muted); }
.aos-stat-row .value { font-weight: 700; color: var(--aos-text); }
.aos-stat-row.win .label { color: var(--aos-blue); font-weight: 600; }
.aos-stat-row.win .value { color: var(--aos-blue); }
</style>
"""


def inject_theme() -> None:
    """Inject the Athlete OS CSS design system. Call once, right after st.set_page_config."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def mdbold(text: str) -> str:
    """Convert **bold** markdown syntax to <b>bold</b> for safe use inside raw-HTML cards."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def render_insight_card(category: str, html_text: str) -> None:
    """A single categorized insight rendered as a left-accented card instead of a plain bullet."""
    st.markdown(
        f'<div class="aos-insight"><span class="aos-insight-category">{category}</span>{html_text}</div>',
        unsafe_allow_html=True,
    )


def render_eyebrow(label: str) -> None:
    """Small uppercase label placed above a section heading."""
    st.markdown(f'<span class="aos-eyebrow">{label}</span>', unsafe_allow_html=True)
