from __future__ import annotations

from html import escape

import streamlit as st

DATA_CLEANING_TOOL_URL = "https://example.com/data-cleaning-tool"

FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Syne:wght@500;600;700;800&display=swap" rel="stylesheet">
"""

CSS = r"""
<style>
  :root {
    --era-bg: #050505;
    --era-ink: #F3F1EC;
    --era-muted: rgba(243,241,236,0.58);
    --era-hair: rgba(255,255,255,0.10);
    --era-shell: rgba(255,255,255,0.045);
    --era-core: #0A0A0C;
    --era-teal: #5EEAD4;
    --era-violet: #C4B5FD;
    --era-ease: cubic-bezier(0.32, 0.72, 0, 1);
  }

  html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--era-bg) !important;
    color: var(--era-ink) !important;
    font-family: "Plus Jakarta Sans", sans-serif !important;
  }

  .stApp {
    min-height: 100dvh;
  }

  .stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background:
      radial-gradient(ellipse 55% 40% at 12% -10%, rgba(94,234,212,0.16), transparent 58%),
      radial-gradient(ellipse 45% 38% at 92% 8%, rgba(167,139,250,0.18), transparent 55%),
      radial-gradient(ellipse 40% 30% at 70% 95%, rgba(94,234,212,0.07), transparent 60%);
  }

  .stApp::after {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 1;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  header[data-testid="stHeader"] {
    background: transparent !important;
  }

  [data-testid="stToolbar"] { right: 1.25rem !important; }

  .stDeployButton,
  .stAppDeployButton,
  [data-testid="stAppDeployButton"],
  [data-testid="stDecoration"] { display: none !important; }

  .block-container {
    padding: 4.5rem 2.4rem 6rem !important;
    max-width: 1180px !important;
    position: relative;
    z-index: 2;
  }

  @media (max-width: 768px) {
    .block-container {
      padding: 2rem 1rem 4rem !important;
      width: 100% !important;
    }
  }

  h1, h2, h3, .era-display {
    font-family: "Syne", sans-serif !important;
    letter-spacing: -0.045em !important;
    font-weight: 700 !important;
    color: var(--era-ink) !important;
  }

  p, label, span, li, .stMarkdown, [data-testid="stCaption"] {
    font-family: "Plus Jakarta Sans", sans-serif !important;
  }

  [data-testid="stCaption"] {
    color: var(--era-muted) !important;
    letter-spacing: 0.01em;
  }

  /* Floating glass sidebar island */
  [data-testid="stSidebar"] {
    background: transparent !important;
  }

  [data-testid="stSidebar"] > div:first-child {
    background: rgba(8,8,10,0.72) !important;
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    margin: 1.25rem 0.85rem !important;
    border-radius: 2rem !important;
    border: 1px solid var(--era-hair) !important;
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.12);
  }

  [data-testid="stSidebarContent"] {
    padding: 1.6rem 1.15rem 2rem !important;
  }

  /* Uploader as machined tray */
  [data-testid="stFileUploaderDropzone"] {
    background: var(--era-core) !important;
    border: 1px solid var(--era-hair) !important;
    border-radius: calc(2rem - 0.375rem) !important;
    min-height: 9.5rem !important;
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.12);
    transition: transform 700ms var(--era-ease), opacity 700ms var(--era-ease);
  }

  [data-testid="stFileUploader"] {
    background: var(--era-shell);
    border: 1px solid var(--era-hair);
    border-radius: 2rem;
    padding: 0.4rem;
  }

  [data-testid="stFileUploaderDropzone"]:hover {
    transform: scale(0.995);
  }

  [data-testid="stFileUploaderDropzone"] * {
    color: var(--era-muted) !important;
    font-family: "Plus Jakarta Sans", sans-serif !important;
  }

  /* Island buttons */
  .stButton > button,
  .stDownloadButton > button,
  [data-testid="stBaseButton-primary"],
  [data-testid="stBaseButton-secondary"] {
    font-family: "Plus Jakarta Sans", sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    font-size: 0.72rem !important;
    border-radius: 999px !important;
    padding: 0.85rem 1.5rem !important;
    border: 1px solid var(--era-hair) !important;
    background: linear-gradient(180deg, #141416, #0B0B0D) !important;
    color: var(--era-ink) !important;
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.16);
    transition: transform 700ms var(--era-ease), opacity 700ms var(--era-ease);
  }

  .stButton > button[kind="primary"],
  [data-testid="stBaseButton-primary"] {
    background: linear-gradient(180deg, #F3F1EC, #D9D4C8) !important;
    color: #111 !important;
    border-color: transparent !important;
  }

  .stButton > button:hover,
  .stDownloadButton > button:hover {
    transform: scale(1.015);
  }

  .stButton > button:active,
  .stDownloadButton > button:active {
    transform: scale(0.98);
  }

  /* Tabs */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.4rem;
    background: var(--era-shell);
    border: 1px solid var(--era-hair);
    border-radius: 999px;
    padding: 0.35rem;
  }

  [data-testid="stTabs"] button {
    font-family: "Plus Jakarta Sans", sans-serif !important;
    border-radius: 999px !important;
    color: var(--era-muted) !important;
  }

  [data-testid="stTabs"] button[aria-selected="true"] {
    background: #141416 !important;
    color: var(--era-ink) !important;
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.12);
  }

  [data-testid="stDataFrame"],
  [data-testid="stSelectbox"] > div {
    border-radius: 1.15rem !important;
    overflow: hidden;
  }

  div[data-baseweb="select"] > div {
    background: var(--era-core) !important;
    border: 1px solid var(--era-hair) !important;
    border-radius: 1.15rem !important;
  }

  [data-testid="stAlertContainer"],
  [data-testid="stAlertContentInfo"] {
    background: var(--era-core) !important;
    color: var(--era-ink) !important;
  }

  [data-testid="stPlotlyChart"] {
    background: transparent !important;
  }

  .js-plotly-plot .plotly { background: transparent !important; }

  /* Custom atoms */
  .era-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border-radius: 999px;
    padding: 0.28rem 0.72rem;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--era-teal);
    background: rgba(94,234,212,0.08);
    border: 1px solid rgba(94,234,212,0.18);
    margin-bottom: 1.1rem;
  }

  .era-hero {
    display: grid;
    grid-template-columns: 1.35fr 0.85fr;
    gap: 2.4rem;
    align-items: end;
    margin: 0 0 3.5rem;
    animation: era-enter 900ms var(--era-ease) both;
  }

  @media (max-width: 768px) {
    .era-hero {
      grid-template-columns: 1fr;
      gap: 1.4rem;
    }
  }

  .era-hero h1 {
    font-size: clamp(2.6rem, 6vw, 4.6rem) !important;
    line-height: 0.92 !important;
    margin: 0 0 1rem !important;
  }

  .era-lede {
    font-size: 1.05rem;
    line-height: 1.65;
    color: var(--era-muted);
    max-width: 36rem;
  }

  .era-hero-aside {
    color: var(--era-muted);
    font-size: 0.92rem;
    line-height: 1.7;
    padding-bottom: 0.35rem;
  }

  .era-hero-aside strong { color: var(--era-ink); font-weight: 600; }

  .era-section {
    margin: 3.2rem 0 1.4rem;
    animation: era-enter 900ms var(--era-ease) both;
  }

  .era-section h2 {
    font-size: clamp(1.6rem, 3vw, 2.15rem) !important;
    margin: 0 0 0.45rem !important;
  }

  .era-shell {
    background: var(--era-shell);
    border: 1px solid var(--era-hair);
    border-radius: 2rem;
    padding: 0.4rem;
  }

  .era-core {
    background: var(--era-core);
    border-radius: calc(2rem - 0.375rem);
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.14);
    padding: 1.35rem 1.45rem;
  }

  .era-bento {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 0.85rem;
    margin: 0.4rem 0 1.6rem;
  }

  .era-tile { grid-column: span 3; }
  .era-tile-lg { grid-column: span 6; }

  @media (max-width: 768px) {
    .era-bento { grid-template-columns: 1fr; }
    .era-tile, .era-tile-lg { grid-column: span 1; }
  }

  .era-kicker {
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--era-violet);
    margin-bottom: 0.55rem;
  }

  .era-value {
    font-family: "Syne", sans-serif;
    font-size: 2.05rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 1;
  }

  .era-insight-wrap {
    margin: 0.65rem 0;
    animation: era-enter 900ms var(--era-ease) both;
  }
    grid-template-columns: auto 1fr;
    gap: 0.9rem;
    align-items: start;
    margin: 0.65rem 0;
    animation: era-enter 900ms var(--era-ease) both;
  }

  .era-index {
    font-family: "Syne", sans-serif;
    font-size: 0.85rem;
    color: var(--era-teal);
    min-width: 1.8rem;
    padding-top: 0.15rem;
  }

  .era-insight p {
    margin: 0;
    font-size: 1.02rem;
    line-height: 1.55;
    color: var(--era-ink);
  }

  .era-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    border-radius: 999px;
    padding: 0.45rem 0.45rem 0.45rem 1.05rem;
    background: linear-gradient(180deg, #F3F1EC, #D9D4C8);
    color: #111 !important;
    text-decoration: none !important;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    transition: transform 700ms var(--era-ease);
  }

  .era-cta:hover { transform: scale(1.02); }
  .era-cta:active { transform: scale(0.98); }

  .era-cta-icon {
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    background: rgba(0,0,0,0.08);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    transition: transform 700ms var(--era-ease);
  }

  .era-cta:hover .era-cta-icon {
    transform: translateX(3px) translateY(-1px) scale(1.05);
  }

  .era-side-title {
    font-family: "Syne", sans-serif;
    font-size: 1.35rem;
    letter-spacing: -0.04em;
    margin: 0 0 1rem;
  }

  .era-steps {
    list-style: none;
    padding: 0;
    margin: 0 0 1.6rem;
  }

  .era-steps li {
    display: grid;
    grid-template-columns: 1.6rem 1fr;
    gap: 0.55rem;
    margin: 0 0 0.85rem;
    color: var(--era-muted);
    font-size: 0.9rem;
    line-height: 1.45;
  }

  .era-steps b { color: var(--era-teal); font-family: "Syne", sans-serif; font-weight: 600; }

  .era-note {
    color: var(--era-muted);
    font-size: 0.88rem;
    line-height: 1.55;
    margin-bottom: 1rem;
  }

  @keyframes era-enter {
    from { opacity: 0; transform: translateY(2.4rem); }
    to { opacity: 1; transform: translateY(0); }
  }

  footer { visibility: hidden; }
</style>
"""


def inject_theme() -> None:
    st.markdown(FONTS + CSS, unsafe_allow_html=True)


def section_header(eyebrow: str, title: str, lede: str = "") -> None:
    lede_html = f'<p class="era-lede">{escape(lede)}</p>' if lede else ""
    st.markdown(
        f"""
        <div class="era-section">
          <div class="era-eyebrow">{escape(eyebrow)}</div>
          <h2>{escape(title)}</h2>
          {lede_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero() -> None:
    st.markdown(
        """
        <div class="era-hero">
          <div>
            <div class="era-eyebrow">Analyst briefing · no model API</div>
            <h1>The spreadsheet,<br>spoken plainly.</h1>
            <p class="era-lede">
              Upload a workbook. We read the grain of the data and write the
              findings a senior analyst would put on slide one — missingness,
              outliers, drift, the relationships that actually matter.
            </p>
          </div>
          <div class="era-hero-aside">
            <strong>What you leave with.</strong><br>
            A profile of every column, charts that follow the story,
            and a shareable Excel + PDF briefing — generated in one pass.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_chrome() -> None:
    st.markdown(
        f"""
        <div class="era-eyebrow">Protocol</div>
        <div class="era-side-title">How this works</div>
        <ol class="era-steps">
          <li><b>01</b><span>Drop an .xlsx, .xls, or .csv</span></li>
          <li><b>02</b><span>Choose a sheet if the file has several</span></li>
          <li><b>03</b><span>Read Key Insights first — that is the briefing</span></li>
          <li><b>04</b><span>Export Excel + PDF when you need a file to send</span></li>
        </ol>
        <p class="era-note">Data looking messy? Clean it before you brief.</p>
        <a class="era-cta" href="{DATA_CLEANING_TOOL_URL}">
          Data Cleaning Tool
          <span class="era-cta-icon">↗</span>
        </a>
        """,
        unsafe_allow_html=True,
    )


def bento_metrics(rows: int, columns: int, duplicates: int, missing_pct: float) -> None:
    specs = [
        ("era-tile-lg", "Volume", f"{rows:,}", "Rows in the selected sheet"),
        ("era-tile", "Structure", f"{columns:,}", "Columns detected"),
        ("era-tile", "Copies", f"{duplicates:,}", "Duplicate rows"),
        ("era-tile-lg", "Integrity", f"{missing_pct:.1f}%", "Cells empty across the whole grid"),
    ]
    html = ['<div class="era-bento">']
    for cls, kicker, value, hint in specs:
        html.append(
            f"""
            <div class="{cls}">
              <div class="era-shell">
                <div class="era-core">
                  <div class="era-kicker">{escape(kicker)}</div>
                  <div class="era-value">{escape(value)}</div>
                  <p class="era-note" style="margin:0.65rem 0 0">{escape(hint)}</p>
                </div>
              </div>
            </div>
            """
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def insight_cards(insights: list[str]) -> None:
    if not insights:
        st.markdown(
            """
            <div class="era-shell">
              <div class="era-core">
                <div class="era-kicker">Clean pass</div>
                <p class="era-lede" style="margin:0">No notable issues detected — this dataset looks clean.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    blocks = []
    for i, sentence in enumerate(insights, start=1):
        delay = min(i * 80, 480)
        blocks.append(
            f"""
            <div class="era-shell era-insight-wrap" style="animation-delay:{delay}ms">
              <div class="era-core era-insight">
                <div class="era-index">{i:02d}</div>
                <p>{escape(sentence)}</p>
              </div>
            </div>
            """
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)
