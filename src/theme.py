"""
Visual design system for Athlete OS: a premium, dark, telemetry-inspired
sportive theme.

Native widget theming (backgrounds, sidebar, dataframes, buttons) comes from
.streamlit/config.toml's [theme] block - the robust, version-stable way to
theme Streamlit. This module only layers on top of that for things config.toml
can't reach: the hero banner, KPI card polish, section eyebrows, and insight
cards. No analysis logic lives here - this module is presentation only.
"""

import base64
import re
from pathlib import Path

import streamlit as st

HERO_IMAGE_PATH = Path(__file__).resolve().parent.parent / "assets" / "athlete_os_hero.png"
HERO_MAX_WIDTH = 1600  # downscale target so the embedded data URI stays reasonably small

THEME_CSS = """
<style>
:root {
    --aos-bg: #080B10;
    --aos-sidebar: #0B1016;
    --aos-card: #111820;
    --aos-elevated: #161E28;
    --aos-border: rgba(255, 255, 255, 0.09);
    --aos-text: #F4F7FA;
    --aos-muted: #8E99A8;
    --aos-green: #A6FF4D;
    --aos-cyan: #35D9FF;
    --aos-amber: #FFB547;
    --aos-red: #FF5C5C;
}

/* Atmospheric depth behind the whole app: a noticeable-but-soft cyan wash
   (upper right, echoing the hero/analytical accent), a subtler green wash
   (lower left), an extremely faint telemetry grid, and a soft diagonal
   sheen so the page reads as a lit surface rather than flat black.
   Applied with !important on the actual Streamlit view container (not just
   .stApp) since that's the element the native dark theme paints its solid
   backgroundColor onto - without targeting it directly the gradient layers
   were being rendered underneath/behind that opaque fill. */
.stApp,
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 82% 8%, rgba(53, 217, 255, 0.16) 0%, rgba(53, 217, 255, 0.07) 20%, transparent 42%),
        radial-gradient(circle at 10% 85%, rgba(166, 255, 77, 0.08) 0%, transparent 32%),
        radial-gradient(circle at 100% 0%, transparent 58%, rgba(53, 217, 255, 0.025) 59%, transparent 61%),
        repeating-linear-gradient(0deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, transparent 1px, transparent 48px),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, transparent 1px, transparent 48px),
        linear-gradient(135deg, #080B10 0%, #0A1017 48%, #080B10 100%) !important;
    background-attachment: fixed, fixed, fixed, fixed, fixed, fixed !important;
}

/* Sidebar: darker than the main content, no competing gradient - just a
   crisp separating edge. */
[data-testid="stSidebar"] {
    background: var(--aos-sidebar) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}

/* KPI metric cards */
div[data-testid="stMetric"] {
    background: var(--aos-card);
    border: 1px solid var(--aos-border);
    border-radius: 14px;
    padding: 14px 18px 10px 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
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
    border-radius: 16px !important;
    border-color: var(--aos-border) !important;
    background: var(--aos-card);
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}

/* Elevated "feature" modules - the few sections meant to feel intentionally
   important: the Overview trend/snapshot module, Primary Recovery Signal,
   Cricket vs Gym. Lighter surface + a very restrained cyan glow. */
div[data-testid="stVerticalBlockBorderWrapper"].st-key-feature-performance-trend,
div[data-testid="stVerticalBlockBorderWrapper"].st-key-feature-primary-recovery-signal,
div[data-testid="stVerticalBlockBorderWrapper"].st-key-feature-cricket-vs-gym {
    background: var(--aos-elevated);
    border-color: rgba(53, 217, 255, 0.28) !important;
    box-shadow: 0 10px 30px rgba(0,0,0,0.28), 0 0 18px rgba(53, 217, 255, 0.07);
}

h1 { font-weight: 800; letter-spacing: -0.02em; color: var(--aos-text); }
h2, h3, h4 { font-weight: 700; color: var(--aos-text); }

/* Tabs as a segmented product nav - subtle glow only on the active tab */
button[data-baseweb="tab"] { font-weight: 600; font-size: 0.95rem; }
button[data-baseweb="tab"][aria-selected="true"] {
    text-shadow: 0 0 14px rgba(53, 217, 255, 0.18);
}
div[data-baseweb="tab-highlight"] {
    background-color: var(--aos-cyan) !important;
    height: 3px !important;
    box-shadow: 0 0 10px rgba(53, 217, 255, 0.35);
}

/* Sidebar quick-range buttons: pill shape, restrained active treatment
   (thin cyan border + faint tint) rather than a solid glowing fill. */
.stButton > button { border-radius: 999px; font-weight: 600; }
.stButton > button[kind="primary"] {
    background: rgba(53, 217, 255, 0.08) !important;
    border: 1px solid var(--aos-cyan) !important;
    color: var(--aos-text) !important;
    box-shadow: 0 0 12px rgba(53, 217, 255, 0.10);
}
.stButton > button[kind="secondary"] {
    background: var(--aos-card) !important;
    border: 1px solid var(--aos-border) !important;
    color: var(--aos-muted) !important;
}

/* Small uppercase section label ("eyebrow") */
.aos-eyebrow {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--aos-cyan);
    margin-bottom: 2px;
}

/* Insight cards (Performance Story, Cricket vs Gym observations, ...) */
.aos-insight {
    background: var(--aos-elevated);
    border: 1px solid var(--aos-border);
    border-left: 3px solid var(--aos-cyan);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.93rem;
    line-height: 1.4;
    color: var(--aos-text);
}
.aos-insight b { color: var(--aos-cyan); }
.aos-insight-category {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: var(--aos-muted);
    margin-right: 8px;
}

/* Primary/Key insight callout (glass card, cyan accent) */
.aos-signal-card {
    background: rgba(22, 29, 39, 0.78);
    backdrop-filter: blur(6px);
    border: 1px solid rgba(53, 217, 255, 0.30);
    border-radius: 14px;
    padding: 16px 20px;
    margin: 8px 0 4px 0;
    font-size: 0.98rem;
    line-height: 1.45;
    color: var(--aos-text);
    box-shadow: 0 0 18px rgba(53, 217, 255, 0.07);
}
.aos-signal-card .aos-eyebrow { color: var(--aos-green); }
.aos-signal-card b { color: var(--aos-cyan); }

/* Compact stat rows inside comparison cards (Cricket vs Gym) */
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
.aos-stat-row.win .label { color: var(--aos-cyan); font-weight: 600; }
.aos-stat-row.win .value {
    color: var(--aos-cyan);
    text-shadow: 0 0 10px rgba(53, 217, 255, 0.25);
}

/* DATA & METHODOLOGY: deliberately lower-priority surface than the rest of
   the dashboard - darker, no elevation, no border glow. */
div[data-testid="stExpander"] {
    background: var(--aos-bg);
    border: 1px solid var(--aos-border) !important;
    border-radius: 12px !important;
}
div[data-testid="stExpander"] summary { color: var(--aos-muted); font-weight: 600; }

/* Hero banner */
.aos-hero {
    position: relative;
    border-radius: 20px;
    overflow: hidden;
    min-height: 460px;
    padding: 40px 48px;
    margin-bottom: 8px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background-size: cover;
    background-position: right center;
    background-repeat: no-repeat;
    border: 1px solid var(--aos-border);
    box-shadow: 0 12px 32px rgba(0,0,0,0.28);
}
.aos-hero-eyebrow {
    color: var(--aos-cyan);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.aos-hero-title {
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #ffffff;
    margin: 0 0 6px 0;
    line-height: 1.05;
}
.aos-hero-subtitle {
    font-size: 1.15rem;
    font-weight: 600;
    color: #E4EAF0;
    margin-bottom: 10px;
}
.aos-hero-problem {
    font-size: 0.95rem;
    color: #B7C1CC;
    max-width: 480px;
    line-height: 1.5;
    margin-bottom: 20px;
}
.aos-hero-meta {
    display: flex;
    gap: 32px;
    margin-bottom: 18px;
    flex-wrap: wrap;
}
.aos-hero-meta-item .aos-eyebrow { color: var(--aos-cyan); margin-bottom: 4px; }
.aos-hero-meta-value {
    font-size: 1rem;
    font-weight: 700;
    color: #ffffff;
}
.aos-hero-signal {
    max-width: 520px;
}

/* ============================================================
   RESPONSIVE / MOBILE
   Desktop styling above 768px is untouched by everything below.
   Strategy: a safe blanket fallback (every column stacks full-width
   on narrow screens, so nothing can overflow), then a few explicit,
   opt-in overrides - via .st-key-* wrapper classes set through
   st.container(key=...) in app.py - for the handful of sections that
   want a 2-column grid or a natural wrap instead of a full stack.
   ============================================================ */
@media (max-width: 768px) {
    html, body, .stApp { overflow-x: hidden; }

    [data-testid="stMainBlockContainer"], .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 1rem !important;
    }

    /* Slightly calmer atmospheric background on small screens - same
       identity, less visual noise on a small panel. */
    .stApp, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 82% 8%, rgba(53, 217, 255, 0.11) 0%, rgba(53, 217, 255, 0.05) 20%, transparent 42%),
            radial-gradient(circle at 10% 85%, rgba(166, 255, 77, 0.05) 0%, transparent 32%),
            repeating-linear-gradient(0deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 1px, transparent 1px, transparent 48px),
            repeating-linear-gradient(90deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 1px, transparent 1px, transparent 48px),
            linear-gradient(135deg, #080B10 0%, #0A1017 48%, #080B10 100%) !important;
    }

    /* Safe default: every column-based row stacks to full width so
       nothing can force horizontal overflow. Specific .st-key-*
       wrappers below opt back into a grid/wrap layout deliberately. */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: 10px !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 0 !important;
    }

    /* KPI telemetry grids: 2-per-row on mobile instead of a full stack.
       Selectors are written to match the blanket fallback rule's shape
       (parent > child, same selector "weight") so these - being scoped
       under a more specific ancestor class - reliably win the cascade. */
    .st-key-kpi-grid div[data-testid="stHorizontalBlock"],
    .st-key-kpi-grid-training div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 10px !important;
    }
    .st-key-kpi-grid div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
    .st-key-kpi-grid-training div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 46% !important;
        width: 46% !important;
        min-width: 140px !important;
    }

    /* AI suggested-question pills: wrap naturally, sized to their text,
       instead of stacking one-per-line or being squeezed onto one row. */
    .st-key-ai-suggestions-grid div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    .st-key-ai-suggestions-grid div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 0 1 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    .st-key-ai-suggestions-grid .stButton > button {
        width: auto !important;
        white-space: nowrap;
    }

    /* Hero */
    .aos-hero {
        min-height: 300px;
        padding: 26px 20px;
        border-radius: 16px;
        background-position: right center;
    }
    .aos-hero-title { font-size: clamp(28px, 9vw, 36px); }
    .aos-hero-subtitle { font-size: 15px; }
    .aos-hero-problem { font-size: 13px; max-width: 100%; margin-bottom: 14px; }
    .aos-hero-meta { gap: 16px; margin-bottom: 14px; }
    .aos-hero-meta-value { font-size: 0.9rem; }
    .aos-hero-signal { max-width: 100%; padding: 12px 16px; }

    /* Tabs: compact, and horizontally swipeable (not the whole page)
       if three labels still can't fit a very narrow screen. */
    button[data-baseweb="tab"] {
        font-size: 0.8rem !important;
        padding: 10px 10px !important;
        min-height: 44px;
    }
    div[data-baseweb="tab-list"] {
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        flex-wrap: nowrap !important;
    }

    /* Metric cards: tighter but still readable, no clipped values. */
    div[data-testid="stMetric"] { padding: 10px 12px 8px 12px; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem; overflow-wrap: anywhere; }
    div[data-testid="stMetricLabel"] { font-size: 0.68rem; }

    /* Cards/containers generally */
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 4px; }
    .aos-hero, div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stMetric"] {
        max-width: 100%;
        box-sizing: border-box;
    }

    /* Tables/dataframes scroll within themselves, never the page. */
    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        max-width: 100%;
        overflow-x: auto;
    }

    /* File uploader + AI evidence text stay within the card. */
    div[data-testid="stFileUploaderDropzone"] { max-width: 100%; }
    .aos-insight, .aos-signal-card { max-width: 100%; box-sizing: border-box; }

    /* Comfortable tap targets. */
    .stButton > button, .stDownloadButton > button {
        min-height: 42px;
    }

    img { max-width: 100%; height: auto; }
}

@media (max-width: 480px) {
    .aos-hero { min-height: 270px; padding: 22px 16px; }
    .aos-hero-title { font-size: clamp(26px, 10vw, 32px); }
}

/* Very narrow phones: KPI grid gracefully falls back to one column.
   (Selector shape matched to the 768px override above so specificity
   ties resolve correctly rather than losing to the wider-viewport rule.) */
@media (max-width: 400px) {
    .st-key-kpi-grid div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
    .st-key-kpi-grid-training div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        width: 100% !important;
    }
}
</style>
"""


@st.cache_resource(show_spinner=False)
def _load_hero_background_data_uri() -> str | None:
    """
    Base64 data URI for the hero background image, downscaled for a smaller
    payload. Returns None (triggering a gradient-only fallback) if the file
    is missing or can't be processed for any reason - base64 embedding is a
    deliberate choice here since Streamlit doesn't serve arbitrary project
    files over HTTP, so a plain url("assets/...") would not resolve.
    """
    if not HERO_IMAGE_PATH.exists():
        return None

    try:
        from PIL import Image
        import io

        img = Image.open(HERO_IMAGE_PATH).convert("RGB")
        if img.width > HERO_MAX_WIDTH:
            ratio = HERO_MAX_WIDTH / img.width
            img = img.resize((HERO_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        try:
            raw = HERO_IMAGE_PATH.read_bytes()
            encoded = base64.b64encode(raw).decode("ascii")
            return f"data:image/png;base64,{encoded}"
        except Exception:
            return None


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


def metric_context_html(text: str, color: str = "var(--aos-muted)") -> str:
    """Small uppercase contextual note rendered directly beneath a KPI card (e.g. 'GREEN RANGE')."""
    return (
        f'<div style="font-size:0.68rem; font-weight:700; letter-spacing:.04em; '
        f'color:{color}; margin-top:-6px; margin-bottom:4px;">{text}</div>'
    )


def render_eyebrow(label: str) -> None:
    """Small uppercase label placed above a section heading."""
    st.markdown(f'<span class="aos-eyebrow">{label}</span>', unsafe_allow_html=True)


def render_hero(
    meta_items: list[tuple[str, str]],
    signal_html: str | None,
    eyebrow: str = "PERFORMANCE LAB",
    title: str = "ATHLETE OS",
    subtitle: str = "Performance Intelligence for Training, Recovery &amp; Sleep",
    problem_sentence: str = (
        "Turning wearable data into clear signals about recovery, training load, "
        "and athletic performance."
    ),
) -> None:
    """
    Premium hero banner: local background image (base64, gracefully falls
    back to a dark gradient if the asset is missing) with a readable dark
    overlay on the left, title/subtitle/meta row, and an optional Primary
    Performance Signal glass card - all rendered in one HTML block so it
    actually nests correctly rather than relying on multi-call div wrapping.
    """
    image_uri = _load_hero_background_data_uri()

    # Overlay stops match --aos-bg (#080B10) so the hero's dark side reads as
    # a continuation of the page background rather than a separate poster.
    overlay = (
        "linear-gradient(90deg, rgba(8,11,16,0.97) 0%, rgba(8,11,16,0.88) 35%, "
        "rgba(8,11,16,0.55) 62%, rgba(8,11,16,0.18) 100%)"
    )
    if image_uri:
        background = f"{overlay}, url('{image_uri}')"
    else:
        # Graceful fallback if the hero asset can't be loaded: gradient-only hero,
        # built from the same page/elevated/cyan tokens as the rest of the app.
        background = "linear-gradient(120deg, #080B10 0%, #161D27 55%, #163044 100%)"

    meta_html = "".join(
        f'<div class="aos-hero-meta-item"><div class="aos-eyebrow">{label}</div>'
        f'<div class="aos-hero-meta-value">{value}</div></div>'
        for label, value in meta_items
    )

    signal_block = ""
    if signal_html:
        signal_block = (
            '<div class="aos-hero-signal aos-signal-card">'
            '<div class="aos-eyebrow">Primary Performance Signal</div>'
            f'{signal_html}</div>'
        )

    st.markdown(
        f'<div class="aos-hero" style="background-image: {background};">'
        f'<div class="aos-hero-eyebrow">{eyebrow}</div>'
        f'<div class="aos-hero-title">{title}</div>'
        f'<div class="aos-hero-subtitle">{subtitle}</div>'
        f'<div class="aos-hero-problem">{problem_sentence}</div>'
        f'<div class="aos-hero-meta">{meta_html}</div>'
        f'{signal_block}'
        f'</div>',
        unsafe_allow_html=True,
    )
