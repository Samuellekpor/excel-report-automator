from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insights import classify_columns, coerce_datetime
from ui import section_header


@st.cache_data(show_spinner=False)
def cached_classify_columns(df: pd.DataFrame):
    return classify_columns(df)

# Names match the Google Fonts <link> in inject_theme() (ui.py). Fallbacks
# keep Plotly readable if a family does not load inside the chart surface.
_CHART_SANS = "Plus Jakarta Sans, ui-sans-serif, system-ui, sans-serif"
_CHART_DISPLAY = "Syne, Plus Jakarta Sans, ui-sans-serif, system-ui, sans-serif"

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0A0A0C",
    font=dict(family=_CHART_SANS, color="#F3F1EC", size=12),
    title=dict(font=dict(family=_CHART_DISPLAY, size=16, color="#F3F1EC")),
    margin=dict(l=40, r=24, t=56, b=40),
    colorway=["#5EEAD4", "#C4B5FD", "#F3F1EC", "#67E8F9"],
)

# Diverging like RdBu, reskinned: teal (negative) ↔ cream (zero) ↔ purple
# (positive). Cream sits above the plot background so |r|≈0 still reads.
CORR_COLORSCALE = [
    [0.0, "#0F766E"],
    [0.25, "#5EEAD4"],
    [0.5, "#F3F1EC"],
    [0.75, "#C4B5FD"],
    [1.0, "#6D28D9"],
]

# Keep in sync with reports._chart_images.
MAX_NUMERIC_CHARTS = 8
MAX_CATEGORY_CHARTS = 8
MAX_TIMESERIES_CHARTS = 4
MAX_CORR_COLUMNS = 12


def _style(fig, **layout) -> None:
    fig.update_layout(**CHART_LAYOUT, **layout)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.08)")


def render_charts(df: pd.DataFrame) -> None:
    section_header(
        "03  ·  Charts",
        "See the patterns",
        "How values are spread, which categories show up most, how columns move together, and change over time — only when the data supports them.",
    )
    types = cached_classify_columns(df)
    numeric_cols = types["numeric"][:MAX_NUMERIC_CHARTS]
    cat_cols = types["categorical"][:MAX_CATEGORY_CHARTS]
    ts_cols = types["numeric"][:MAX_TIMESERIES_CHARTS]
    corr_cols = types["numeric"][:MAX_CORR_COLUMNS]

    if numeric_cols:
        st.markdown("### How numbers are spread")
        if len(types["numeric"]) > len(numeric_cols):
            st.caption(f"Showing {len(numeric_cols)} of {len(types['numeric'])} number columns.")
        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            fig = px.histogram(series, x=series.name or col, nbins=30, title=f"Spread of {col}")
            _style(fig, xaxis_title=col, yaxis_title="Count", bargap=0.05)
            fig.update_traces(marker_color="#5EEAD4", marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    if cat_cols:
        st.markdown("### Most common values")
        if len(types["categorical"]) > len(cat_cols):
            st.caption(f"Showing {len(cat_cols)} of {len(types['categorical'])} category columns.")
        for col in cat_cols:
            counts = df[col].dropna().astype(str).value_counts().head(10)
            if counts.empty:
                continue
            fig = px.bar(
                x=counts.index.astype(str),
                y=counts.values,
                title=f"Top 10 values in {col}",
                labels={"x": col, "y": "Count"},
            )
            _style(fig)
            fig.update_traces(marker_color="#C4B5FD")
            st.plotly_chart(fig, use_container_width=True)

    if len(corr_cols) >= 2:
        st.markdown("### How numbers move together")
        corr = df[corr_cols].apply(pd.to_numeric, errors="coerce").corr()
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=list(corr.columns),
                y=list(corr.index),
                colorscale=CORR_COLORSCALE,
                zmid=0,
                zmin=-1,
                zmax=1,
                colorbar=dict(title="r"),
            )
        )
        _style(fig, title="Correlation between number columns")
        st.plotly_chart(fig, use_container_width=True)

    if types["datetime"] and ts_cols:
        st.markdown("### Change over time")
        date_col = types["datetime"][0]
        dates = coerce_datetime(df[date_col])
        for num_col in ts_cols:
            paired = pd.DataFrame(
                {"date": dates, "value": pd.to_numeric(df[num_col], errors="coerce")}
            ).dropna()
            if paired.empty or paired["date"].nunique() < 2:
                continue
            paired = paired.sort_values("date").groupby("date", as_index=False)["value"].mean()
            fig = px.line(
                paired,
                x="date",
                y="value",
                title=f"{num_col} over time ({date_col})",
                markers=True,
            )
            _style(fig, xaxis_title=date_col, yaxis_title=num_col)
            fig.update_traces(line_color="#5EEAD4", line_width=2.4)
            st.plotly_chart(fig, use_container_width=True)

    if not types["numeric"] and not types["categorical"]:
        st.info("Nothing here to chart — this sheet has no number or category columns.")
