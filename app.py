"""
Career Intelligence Agent – Modern SaaS Dashboard
Single-page, light theme, no sidebar, vertical scroll experience.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import html as _html
import io
import os
import time
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Career Intelligence Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Design tokens ── */
:root {
    --accent:      #4F46E5;
    --accent-h:    #4338CA;
    --accent-lite: #EEF2FF;
    --accent-mid:  #C7D2FE;
    --bg:          #F7F8FC;
    --card:        #FFFFFF;
    --border:      #E2E8F0;
    --text:        #1A202C;
    --text-2:      #64748B;
    --text-3:      #94A3B8;
    --green:       #10B981;
    --green-lite:  #D1FAE5;
    --green-bdr:   #A7F3D0;
    --yellow:      #F59E0B;
    --yellow-lite: #FEF3C7;
    --yellow-bdr:  #FCD34D;
    --red:         #EF4444;
    --red-lite:    #FEE2E2;
    --red-bdr:     #FCA5A5;
    --sh-sm: 0 1px 2px rgba(0,0,0,.05);
    --sh:    0 1px 3px rgba(0,0,0,.10), 0 1px 2px rgba(0,0,0,.06);
    --sh-md: 0 4px 6px -1px rgba(0,0,0,.10), 0 2px 4px -1px rgba(0,0,0,.06);
    --sh-lg: 0 10px 15px -3px rgba(0,0,0,.10), 0 4px 6px -2px rgba(0,0,0,.05);
    --sh-xl: 0 20px 60px -12px rgba(79,70,229,.20);
    --r:    12px;
    --r-sm:  8px;
    --r-lg: 16px;
    --r-xl: 24px;
}

/* ── Global reset ── */
*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: var(--bg) !important;
    color: var(--text) !important;
}

/* ── Kill Streamlit chrome & sidebar ── */
#MainMenu, footer, header,
[data-testid="stDecoration"],
[data-testid="collapsedControl"],
section[data-testid="stSidebar"]  { display: none !important; }

.block-container { padding: 0 !important; max-width: 100% !important; }

/* ── Sticky nav ── */
.cia-nav {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(255,255,255,.97);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    height: 58px;
    padding: 0 48px;
    gap: 32px;
    box-shadow: var(--sh-sm);
}
.cia-logo {
    font-size: 15px; font-weight: 800;
    color: var(--accent); letter-spacing: -.4px;
    flex-shrink: 0;
}
.cia-logo small { color: var(--text-3); font-weight: 400; font-size: 13px; margin-left: 4px; }
.cia-nav-links { display: flex; gap: 2px; flex: 1; }
.cia-nav-a {
    font-size: 13px; font-weight: 500;
    color: var(--text-2);
    text-decoration: none !important;
    padding: 6px 12px; border-radius: 6px;
    transition: all .15s; white-space: nowrap;
}
.cia-nav-a:hover { background: var(--accent-lite); color: var(--accent); }
.cia-nav-right { margin-left: auto; }

/* ── Hero ── */
.cia-hero {
    background: linear-gradient(150deg, #f0f4ff 0%, #fafbff 60%, #f0fdf8 100%);
    border-bottom: 1px solid var(--border);
    padding: 36px 48px 24px;
    text-align: center;
}
.cia-eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--accent-lite);
    border: 1px solid var(--accent-mid);
    color: var(--accent);
    border-radius: 20px; padding: 5px 14px;
    font-size: 12px; font-weight: 600;
    letter-spacing: .3px; margin-bottom: 12px;
}
.cia-h1 {
    font-size: 40px; font-weight: 800;
    color: var(--text); line-height: 1.1;
    letter-spacing: -1px; margin-bottom: 10px;
}
.cia-h1 em { color: var(--accent); font-style: normal; }
.cia-hero-sub {
    font-size: 16px; font-weight: 400;
    color: var(--text-2); line-height: 1.65;
    margin: 0 auto 24px; max-width: 540px;
}

/* ── Form card (st.form container) ── */
[data-testid="stForm"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-xl) !important;
    padding: 36px 40px 40px !important;
    box-shadow: var(--sh-xl) !important;
}
.form-title {
    font-size: 20px; font-weight: 700; color: var(--text);
    margin-bottom: 4px;
}
.form-sub {
    font-size: 13px; color: var(--text-3);
    margin-bottom: 24px;
}

/* ── Sections ── */
.cia-section       { padding: 56px 48px; background: var(--card); border-top: 1px solid var(--border); }
.cia-section-alt   { padding: 56px 48px; background: var(--bg);   border-top: 1px solid var(--border); }

.cia-sh {
    display: flex; align-items: flex-start;
    gap: 14px; margin-bottom: 32px;
}
.cia-sh-icon {
    width: 44px; height: 44px; flex-shrink: 0;
    background: var(--accent-lite);
    border: 1px solid var(--accent-mid);
    border-radius: var(--r-sm);
    display: flex; align-items: center;
    justify-content: center; font-size: 22px;
}
.cia-sh-title { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.2; }
.cia-sh-sub   { font-size: 14px; color: var(--text-3); margin-top: 3px; }

/* ── Metric grid ── */
.m-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin-bottom: 28px;
}
.m-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 22px 24px;
    box-shadow: var(--sh-sm);
    position: relative; overflow: hidden;
}
.m-top {
    position: absolute; top: 0; left: 0; right: 0;
    height: 3px; border-radius: var(--r) var(--r) 0 0;
}
.m-val { font-size: 36px; font-weight: 800; color: var(--text); line-height: 1; margin-top: 4px; }
.m-lbl { font-size: 12px; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: .6px; margin-top: 8px; }
.m-sub { font-size: 13px; font-weight: 500; margin-top: 6px; }

/* ── Summary / insight box ── */
.cia-summary {
    background: linear-gradient(135deg, #fafbff, #eef2ff);
    border: 1px solid var(--accent-mid);
    border-radius: var(--r);
    padding: 24px 28px;
    font-size: 15px; line-height: 1.85;
    color: var(--text);
}

/* ── Info card (2-col layout) ── */
.ic-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.cia-ic {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 20px 22px;
    box-shadow: var(--sh-sm);
}
.cia-ic-lbl {
    font-size: 11px; font-weight: 700;
    color: var(--text-3); text-transform: uppercase;
    letter-spacing: .6px; margin-bottom: 10px;
}
.cia-ic-val { font-size: 14px; color: var(--text-2); line-height: 1.65; }

/* ── Tags ── */
.cia-tag {
    display: inline-block;
    font-size: 12px; font-weight: 500;
    padding: 5px 12px; border-radius: 20px; margin: 3px;
}
.t-blue   { background: var(--accent-lite);  color: var(--accent); border: 1px solid var(--accent-mid); }
.t-green  { background: var(--green-lite);   color: #065f46;       border: 1px solid var(--green-bdr); }
.t-red    { background: var(--red-lite);     color: #991b1b;       border: 1px solid var(--red-bdr); }
.t-yellow { background: var(--yellow-lite);  color: #92400e;       border: 1px solid var(--yellow-bdr); }

/* ── Job card ── */
.cia-job {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 20px 24px; margin-bottom: 12px;
    box-shadow: var(--sh-sm);
    transition: all .2s;
}
.cia-job:hover { box-shadow: var(--sh-md); border-color: var(--accent-mid); transform: translateY(-1px); }
.cia-job-t { font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 3px; }
.cia-job-c { font-size: 14px; color: var(--text-2); }
.cia-job-m { font-size: 12px; color: var(--text-3); margin-top: 4px; }

.cia-badge { display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 20px; margin-left: 8px; }
.b-strong  { background: var(--green-lite); color: #065f46; border: 1px solid var(--green-bdr); }
.b-good    { background: var(--yellow-lite); color: #92400e; border: 1px solid var(--yellow-bdr); }
.b-stretch { background: var(--red-lite); color: #991b1b; border: 1px solid var(--red-bdr); }

.bar-bg { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 10px 0; overflow: hidden; }
.bar    { height: 100%; border-radius: 3px; }

.cia-apply {
    display: inline-block; background: var(--accent);
    color: #fff !important; text-decoration: none !important;
    font-size: 13px; font-weight: 600;
    padding: 7px 18px; border-radius: var(--r-sm);
    transition: background .15s;
}
.cia-apply:hover { background: var(--accent-h); }

/* ── Skill gap rows ── */
.cia-gap {
    display: flex; align-items: center; gap: 14px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r-sm); padding: 14px 18px;
    margin-bottom: 8px; box-shadow: var(--sh-sm);
}
.cia-gap-name { flex: 0 0 auto; min-width: 140px; }
.cia-gap-bar  { flex: 1; }
.cia-gap-freq { flex: 0 0 auto; font-size: 12px; color: var(--text-3); font-weight: 500; }

/* ── Roadmap weeks ── */
.cia-week {
    display: flex; gap: 16px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r); padding: 18px 22px;
    margin-bottom: 10px; box-shadow: var(--sh-sm);
}
.cia-week-num {
    flex: 0 0 40px; height: 40px;
    background: var(--accent-lite); border: 1px solid var(--accent-mid);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; color: var(--accent);
}
.cia-week-b   { flex: 1; }
.cia-week-lbl { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 1px; }
.cia-week-f   { font-size: 15px; font-weight: 700; color: var(--text); margin: 3px 0; }
.cia-week-g   { font-size: 13px; color: var(--text-2); line-height: 1.5; }
.cia-week-d   { font-size: 12px; color: var(--text-3); margin-top: 6px; }
.cia-week-res { font-size: 12px; margin-top: 6px; }
.cia-week-res a { color: var(--accent); text-decoration: none; margin-right: 10px; }
.cia-week-res a:hover { text-decoration: underline; }

/* ── Project / cert rows ── */
.pc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.pc-col-lbl {
    font-size: 11px; font-weight: 700;
    color: var(--text-3); text-transform: uppercase;
    letter-spacing: .6px; margin-bottom: 12px;
}
.cia-pc-row {
    display: flex; align-items: flex-start; gap: 12px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r-sm); padding: 14px 16px;
    margin-bottom: 8px; box-shadow: var(--sh-sm);
    font-size: 14px; color: var(--text-2); line-height: 1.5;
}
.pc-icon { flex-shrink: 0; font-size: 17px; }

/* ── Progress step ── */
.cia-progress-step {
    font-size: 13px; font-weight: 500;
    color: var(--accent); padding: 4px 0;
    font-family: 'Inter', sans-serif;
}

/* ── Widget overrides ── */

/* Primary action buttons (Analyze, Clear etc.) */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 13px 28px !important;
    box-shadow: 0 2px 8px rgba(79,70,229,.35) !important;
    letter-spacing: -.1px !important;
    transition: background .15s, box-shadow .15s, transform .15s !important;
    width: 100% !important;
    cursor: pointer !important;
}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    background: var(--accent-h) !important;
    box-shadow: 0 4px 16px rgba(79,70,229,.45) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active,
[data-testid="stFormSubmitButton"] > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 4px rgba(79,70,229,.3) !important;
}

/* Widget labels */
.stTextInput label p,
.stSelectbox label p,
.stFileUploader label p {
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    color: var(--text-2) !important;
    text-transform: uppercase !important;
    letter-spacing: .6px !important;
}

/* Text input */
.stTextInput input {
    background: #ffffff !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    padding: 9px 13px !important;
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,.12) !important;
    background: #ffffff !important;
    outline: none !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background: #ffffff !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    color: var(--text) !important;
}

/* ── File uploader — full zone + Browse button ── */
[data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--r) !important;
    transition: border-color .2s !important;
    padding: 4px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
    background: var(--accent-lite) !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: transparent !important;
    border: none !important;
}
/* The "Browse files" button inside the uploader */
[data-testid="stFileUploaderDropzoneInstructions"] button,
[data-testid="stFileUploader"] section button,
[data-testid="stFileUploader"] button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 20px !important;
    cursor: pointer !important;
    box-shadow: 0 2px 8px rgba(79,70,229,.3) !important;
    transition: background .15s, box-shadow .15s !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] button:hover,
[data-testid="stFileUploader"] section button:hover,
[data-testid="stFileUploader"] button:hover {
    background: var(--accent-h) !important;
    box-shadow: 0 4px 14px rgba(79,70,229,.4) !important;
}
/* Instruction text inside uploader */
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--text-2) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
}

/* Progress bar */
.stProgress > div > div > div > div { background: var(--accent) !important; border-radius: 4px !important; }

/* Alerts */
.stAlert { border-radius: var(--r-sm) !important; font-family: 'Inter', sans-serif !important; }
.stInfo    { background: var(--accent-lite) !important; border-left: 4px solid var(--accent) !important; }
.stSuccess { background: var(--green-lite) !important; border-left: 4px solid var(--green) !important; }
.stWarning { border-left: 4px solid var(--yellow) !important; }

/* Expander */
.streamlit-expanderHeader {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important; font-weight: 500 !important;
    color: var(--text) !important;
}

/* ── Mobile responsive ── */
@media (max-width: 960px) {
    .cia-hero { padding: 28px 24px 16px; }
    .cia-h1 { font-size: 30px; }
    .cia-hero-sub { font-size: 15px; margin-bottom: 16px; }
    .cia-section, .cia-section-alt { padding: 36px 24px; }
    .cia-nav { padding: 0 20px; gap: 16px; }
    .cia-nav-links { display: none; }
    .m-grid { grid-template-columns: repeat(2, 1fr); }
    .ic-grid, .pc-grid { grid-template-columns: 1fr; }
    [data-testid="stForm"] { padding: 24px 20px 28px !important; }
}
@media (max-width: 600px) {
    .m-grid { grid-template-columns: 1fr; }
    .cia-h1 { font-size: 28px; letter-spacing: -.5px; }
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _e(s: object) -> str:
    """HTML-escape a value."""
    return _html.escape(str(s or ""))


def _score_color(score: float) -> str:
    if score >= 0.65:
        return "#10B981"
    if score >= 0.45:
        return "#F59E0B"
    return "#EF4444"


def _badge_cls(tier: str) -> str:
    return {"strong": "b-strong", "good": "b-good"}.get(tier, "b-stretch")


def _tags(skills: list, cls: str = "t-blue") -> str:
    return "".join(
        f'<span class="cia-tag {cls}">{_e(s)}</span>'
        for s in (skills or [])
    )


def _sh(icon: str, title: str, subtitle: str = "") -> str:
    sub = f'<div class="cia-sh-sub">{_e(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="cia-sh">'
        f'  <div class="cia-sh-icon">{icon}</div>'
        f'  <div><div class="cia-sh-title">{_e(title)}</div>{sub}</div>'
        f'</div>'
    )


# ── Nav ───────────────────────────────────────────────────────────────────────

def render_nav(has_results: bool = False) -> None:
    links = ""
    if has_results:
        for anchor, icon, label in [
            ("overview",  "📊", "Overview"),
            ("resume",    "📄", "Resume"),
            ("skills",    "🔧", "Skills"),
            ("jobs",      "💼", "Jobs"),
            ("gaps",      "📈", "Gaps"),
            ("roadmap",   "🗺️", "Roadmap"),
            ("projects",  "🎯", "Projects"),
        ]:
            links += (
                f'<a class="cia-nav-a" href="#{anchor}">'
                f'{icon}&nbsp;{label}</a>'
            )
    st.markdown(
        f'<div class="cia-nav">'
        f'  <div class="cia-logo">🧠 Career Intelligence<small>Agent</small></div>'
        f'  <nav class="cia-nav-links">{links}</nav>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Hero + form ───────────────────────────────────────────────────────────────

def render_hero() -> None:
    st.markdown("""
<div id="hero" class="cia-hero">
  <div class="cia-eyebrow">✨ AI-Powered Career Intelligence</div>
  <h1 class="cia-h1">Turn your résumé into<br><em>career insights</em></h1>
  <p class="cia-hero-sub">
    Upload your PDF and get AI-matched job recommendations,
    personalised skill gap analysis, and a week-by-week learning roadmap
    — all in under 60 seconds.
  </p>
</div>
""", unsafe_allow_html=True)


def render_form() -> dict:
    """Render the analysis form. Returns the collected inputs."""
    _, center, _ = st.columns([0.6, 2.8, 0.6])
    with center:
        with st.form("career_form", clear_on_submit=False):
            st.markdown(
                '<p class="form-title">Start your career analysis</p>'
                '<p class="form-sub">Free &nbsp;·&nbsp; ~60 seconds &nbsp;·&nbsp; No login required</p>',
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "📄  Resume PDF",
                type=["pdf"],
                help="Your file is processed locally and never stored",
            )
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                job_query = st.text_input(
                    "Target Role",
                    placeholder="e.g. Senior Python Developer",
                    help="Leave blank to auto-detect from your resume",
                )
            with c2:
                location = st.text_input("Location", value="Remote India")

            c3, c4 = st.columns(2)
            with c3:
                exp_level = st.selectbox("Experience Level", [
                    "Entry Level  (0–2 years)",
                    "Mid Level    (2–5 years)",
                    "Senior       (5–10 years)",
                    "Principal / Staff  (10+ years)",
                ])
            with c4:
                timeline_str = st.selectbox(
                    "Roadmap Length",
                    ["4 weeks", "8 weeks", "12 weeks", "24 weeks"],
                    index=2,
                )

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "✨  Analyze My Career  →",
                use_container_width=True,
            )

    return {
        "uploaded":    uploaded,
        "job_query":   job_query,
        "location":    location,
        "exp_level":   exp_level,
        "timeline":    int(timeline_str.split()[0]),
        "run":         submitted,
    }


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_analysis(controls: dict) -> dict | None:
    file_bytes = io.BytesIO(controls["uploaded"].read())
    progress = st.progress(0)
    status   = st.empty()

    def on_progress(step: int, label: str) -> None:
        progress.progress(step / 6)
        status.markdown(
            f'<div class="cia-progress-step">Step {step} / 6 — {_e(label)}</div>',
            unsafe_allow_html=True,
        )

    try:
        from agents.career_agent import career_agent
        result = career_agent.run(
            resume_source=file_bytes,
            job_query=controls["job_query"],
            job_location=controls["location"],
            timeline_weeks=controls["timeline"],
            progress_callback=on_progress,
        )
        progress.progress(1.0)
        status.markdown(
            '<div class="cia-progress-step" style="color:#10B981">'
            '✓ Analysis complete!</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.5)
        progress.empty()
        status.empty()
        return result
    except Exception as exc:
        progress.empty()
        status.empty()
        st.error(f"Analysis failed: {exc}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return None


# ── Result sections (pure HTML) ───────────────────────────────────────────────

def render_overview(result: dict) -> None:
    resume     = result.get("resume", {})
    jobs       = result.get("matched_jobs", [])
    gaps       = result.get("skill_gaps", [])
    n_skills   = len(resume.get("skills", []))
    n_jobs     = len(jobs)
    n_gaps     = len(gaps)
    top_score  = f"{jobs[0]['match_score']:.0%}" if jobs else "N/A"
    top_tier   = jobs[0].get("match_tier", "") if jobs else ""
    badge      = f'<span class="cia-badge {_badge_cls(top_tier)}">{top_tier}</span>' if top_tier else ""
    summary    = _e(result.get("career_summary", ""))
    summary_html = (
        f'<div class="cia-summary" style="margin-top:24px">{summary}</div>'
        if summary else ""
    )

    st.markdown(f"""
<div id="overview" class="cia-section">
  {_sh("📊", "Overview", "Your career intelligence snapshot")}
  <div class="m-grid">
    <div class="m-card">
      <div class="m-top" style="background:linear-gradient(90deg,#4F46E5,#818CF8)"></div>
      <div class="m-val">{n_skills}</div>
      <div class="m-lbl">Skills Detected</div>
    </div>
    <div class="m-card">
      <div class="m-top" style="background:linear-gradient(90deg,#10B981,#34D399)"></div>
      <div class="m-val">{n_jobs}</div>
      <div class="m-lbl">Jobs Matched</div>
    </div>
    <div class="m-card">
      <div class="m-top" style="background:linear-gradient(90deg,#F59E0B,#FCD34D)"></div>
      <div class="m-val">{top_score}</div>
      <div class="m-lbl">Top Match Score</div>
      <div class="m-sub">{badge}</div>
    </div>
    <div class="m-card">
      <div class="m-top" style="background:linear-gradient(90deg,#EF4444,#F87171)"></div>
      <div class="m-val">{n_gaps}</div>
      <div class="m-lbl">Skill Gaps Identified</div>
    </div>
  </div>
  {summary_html}
</div>
""", unsafe_allow_html=True)


def render_resume_insights(result: dict) -> None:
    resume     = result.get("resume", {})
    experience = _e(resume.get("experience", "") or "Not extracted from resume")
    education  = _e(resume.get("education",  "") or "Not found in resume")

    st.markdown(f"""
<div id="resume" class="cia-section-alt">
  {_sh("📄", "Resume Insights", "Extracted from your uploaded PDF")}
  <div class="ic-grid">
    <div class="cia-ic">
      <div class="cia-ic-lbl">Experience</div>
      <div class="cia-ic-val">{experience}</div>
    </div>
    <div class="cia-ic">
      <div class="cia-ic-lbl">Education</div>
      <div class="cia-ic-val">{education}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


def render_skills(result: dict) -> None:
    resume = result.get("resume", {})
    skills = resume.get("skills", [])
    tags   = _tags(skills, "t-blue") if skills else (
        '<span style="font-size:14px;color:#94A3B8">No skills detected — '
        'try a more detailed resume.</span>'
    )

    st.markdown(f"""
<div id="skills" class="cia-section">
  {_sh("🔧", "Skills Analysis", f"{len(skills)} skills detected in your resume")}
  <div style="background:var(--bg);border:1px solid var(--border);
              border-radius:var(--r);padding:20px 24px">
    {tags}
  </div>
</div>
""", unsafe_allow_html=True)


def render_jobs(result: dict) -> None:
    jobs = result.get("matched_jobs", [])

    if not jobs:
        st.markdown(f"""
<div id="jobs" class="cia-section-alt">
  {_sh("💼", "Job Matches", "No jobs found — try a different role or location")}
</div>
""", unsafe_allow_html=True)
        return

    cards_html = ""
    for job in jobs:
        score     = job.get("match_score", 0)
        tier      = job.get("match_tier", "stretch")
        color     = _score_color(score)
        pct       = min(100, int(score * 100))

        title     = _e(job.get("title", ""))
        company   = _e(job.get("company", ""))
        loc_txt   = _e(job.get("location", ""))
        salary    = _e(job.get("salary", ""))
        source    = _e(job.get("source", ""))
        url       = job.get("url", "#")

        meta_parts  = [p for p in [loc_txt, salary] if p]
        meta_html   = " &nbsp;·&nbsp; ".join(meta_parts)

        matched_tags = _tags(job.get("matched_skills", [])[:6], "t-green")
        missing_tags = _tags(job.get("missing_skills", [])[:6], "t-red")
        matched_block = matched_tags or '<span style="font-size:13px;color:#94A3B8">None detected</span>'
        missing_block = missing_tags or '<span style="font-size:13px;color:#10B981;font-weight:500">✓ No major gaps</span>'

        via_html = f'<span style="font-size:12px;color:#94A3B8">via {source}</span>' if source else ""

        cards_html += f"""
<div class="cia-job">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
    <div style="flex:1;min-width:0">
      <div class="cia-job-t">{title}<span class="cia-badge {_badge_cls(tier)}">{tier}</span></div>
      <div class="cia-job-c">{company}</div>
      <div class="cia-job-m">{meta_html}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:28px;font-weight:800;color:{color};line-height:1">{score:.0%}</div>
      <div style="font-size:11px;color:#94A3B8;margin-top:2px">match score</div>
    </div>
  </div>
  <div class="bar-bg"><div class="bar" style="width:{pct}%;background:linear-gradient(90deg,{color}77,{color})"></div></div>
  <div style="margin-top:10px">
    <div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px">Matched Skills</div>
    {matched_block}
  </div>
  <div style="margin-top:10px">
    <div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px">Skill Gaps</div>
    {missing_block}
  </div>
  <div style="margin-top:14px;display:flex;gap:12px;align-items:center">
    <a class="cia-apply" href="{url}" target="_blank">&#8594; Apply Now</a>
    {via_html}
  </div>
</div>"""

    st.markdown(f"""
<div id="jobs" class="cia-section-alt">
  {_sh("💼", "Job Matches", f"{len(jobs)} positions matched to your profile")}
  {cards_html}
</div>
""", unsafe_allow_html=True)


def render_gaps(result: dict) -> None:
    gaps = result.get("skill_gaps", [])

    if not gaps:
        st.markdown(f"""
<div id="gaps" class="cia-section">
  {_sh("📈", "Skill Gaps", "No significant gaps found")}
  <div style="background:var(--green-lite);border:1px solid var(--green-bdr);border-radius:var(--r);
              padding:18px 22px;color:#065f46;font-size:15px;font-weight:500">
    ✓ Great news — no significant skill gaps were found for your target role!
  </div>
</div>
""", unsafe_allow_html=True)
        return

    max_p    = max((g.get("priority", 1) for g in gaps), default=1)
    rows_html = ""
    for gap in gaps[:8]:
        skill   = _e(gap.get("skill", ""))
        freq    = gap.get("frequency", 0)
        pct     = int((gap.get("priority", 0) / max_p) * 100) if max_p else 0
        rows_html += f"""
<div class="cia-gap">
  <div class="cia-gap-name"><span class="cia-tag t-red">{skill}</span></div>
  <div class="cia-gap-bar">
    <div class="bar-bg" style="margin:0">
      <div class="bar" style="width:{pct}%;background:linear-gradient(90deg,#FCA5A5,#EF4444)"></div>
    </div>
  </div>
  <div class="cia-gap-freq">Needed by {freq} job{'s' if freq != 1 else ''}</div>
</div>"""

    st.markdown(f"""
<div id="gaps" class="cia-section">
  {_sh("📈", "Skill Gaps", "Skills most frequently required by matching jobs that aren't on your resume")}
  {rows_html}
</div>
""", unsafe_allow_html=True)


def render_roadmap(result: dict) -> None:
    roadmap = result.get("roadmap", {})
    if not roadmap:
        return

    target_role = roadmap.get("target_role", "")
    timeline_w  = roadmap.get("timeline_weeks", 12)
    narrative   = _e(roadmap.get("narrative", ""))
    narr_html   = (
        f'<div class="cia-summary" style="margin-bottom:28px">{narrative}</div>'
        if narrative else ""
    )

    weeks_html = ""
    for i, week in enumerate(roadmap.get("weeks", []), 1):
        focus       = _e(week.get("focus", ""))
        goal        = _e(week.get("goal", ""))
        deliverable = _e(week.get("deliverable", ""))
        week_range  = _e(week.get("week_range", f"Week {i}"))

        res_links = ""
        for r in week.get("resources", [])[:2]:
            parts  = r.split("/")
            domain = parts[2] if len(parts) > 2 else r
            res_links += f'<a href="{r}" target="_blank">{_e(domain)}</a> '

        del_html = f'<div class="cia-week-d">&#128230; {deliverable}</div>' if deliverable else ""
        res_html = f'<div class="cia-week-res">{res_links}</div>' if res_links else ""

        weeks_html += f"""
<div class="cia-week">
  <div class="cia-week-num">{i}</div>
  <div class="cia-week-b">
    <div class="cia-week-lbl">{week_range}</div>
    <div class="cia-week-f">{focus}</div>
    <div class="cia-week-g">{goal}</div>
    {del_html}
    {res_html}
  </div>
</div>"""

    sub = f"Your personalised {timeline_w}-week plan" + (f" to become {_e(target_role)}" if target_role else "")
    st.markdown(f"""
<div id="roadmap" class="cia-section-alt">
  {_sh("🗺️", "Learning Roadmap", sub)}
  {narr_html}
  {weeks_html}
</div>
""", unsafe_allow_html=True)


def render_projects(result: dict) -> None:
    resume   = result.get("resume", {})
    projects = resume.get("projects", [])
    certs    = resume.get("certifications", [])

    if not projects and not certs:
        return

    def _rows(items: list, icon: str) -> str:
        if not items:
            return '<div style="font-size:14px;color:#94A3B8">None found</div>'
        return "".join(
            f'<div class="cia-pc-row"><span class="pc-icon">{icon}</span>'
            f'<span>{_e(str(item))}</span></div>'
            for item in items
        )

    proj_rows = _rows(projects, "🔷")
    cert_rows = _rows(certs, "🏅")

    st.markdown(f"""
<div id="projects" class="cia-section">
  {_sh("🎯", "Projects & Certifications", "Highlights extracted from your resume")}
  <div class="pc-grid">
    <div>
      <div class="pc-col-lbl">Projects</div>
      {proj_rows}
    </div>
    <div>
      <div class="pc-col-lbl">Certifications</div>
      {cert_rows}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    has_results = "result" in st.session_state
    render_nav(has_results=has_results)
    render_hero()
    controls = render_form()

    if controls["run"]:
        if not controls["uploaded"]:
            st.warning("Please upload your resume PDF before running the analysis.")
        else:
            result = run_analysis(controls)
            if result:
                st.session_state["result"] = result
                st.rerun()

    if "result" in st.session_state:
        result = st.session_state["result"]
        render_overview(result)
        render_resume_insights(result)
        render_skills(result)
        render_jobs(result)
        render_gaps(result)
        render_roadmap(result)
        render_projects(result)

        # Clear results button (bottom of page)
        st.markdown('<div class="cia-section-alt" id="bottom">', unsafe_allow_html=True)
        _, btn_col, _ = st.columns([1, 1, 1])
        with btn_col:
            if st.button("🔄  Analyze a Different Resume", key="clear_btn"):
                del st.session_state["result"]
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
