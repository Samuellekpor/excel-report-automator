from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insights import classify_columns, coerce_datetime
from ui import section_header

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


def _style(fig, **layout) -> None:
    fig.update_layout(**CHART_LAYOUT, **layout)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.08)")


def render_charts(df: pd.DataFrame) -> None:
    section_header(
        "03  ·  Evidence",
        "Charts",
        "Distributions, categories, correlation, and time — only where the data supports them.",
    )
    types = classify_columns(df)

    if types["numeric"]:
        st.markdown("### Numeric distributions")
        for col in types["numeric"]:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            fig = px.histogram(series, x=series.name or col, nbins=30, title=f"Histogram — {col}")
            _style(fig, xaxis_title=col, yaxis_title="Count", bargap=0.05)
            fig.update_traces(marker_color="#5EEAD4", marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    cat_cols = types["categorical"] + types["text"]
    if cat_cols:
        st.markdown("### Top categories")
        for col in cat_cols:
            counts = df[col].dropna().astype(str).value_counts().head(10)
            if counts.empty:
                continue
            fig = px.bar(
                x=counts.index.astype(str),
                y=counts.values,
                title=f"Top 10 values — {col}",
                labels={"x": col, "y": "Count"},
            )
            _style(fig)
            fig.update_traces(marker_color="#C4B5FD")
            st.plotly_chart(fig, use_container_width=True)

    if len(types["numeric"]) >= 2:
        st.markdown("### Correlation heatmap")
        corr = df[types["numeric"]].apply(pd.to_numeric, errors="coerce").corr()
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=list(corr.columns),
                y=list(corr.index),
                colorscale=CORR_COLORSCALE,
                zmid=0,
                zmin=-1,
                zmax=1,
                colorbar=dict(title="corr"),
            )
        )
        _style(fig, title="Numeric correlation")
        st.plotly_chart(fig, use_container_width=True)

    if types["datetime"] and types["numeric"]:
        st.markdown("### Time series")
        date_col = types["datetime"][0]
        dates = coerce_datetime(df[date_col])
        for num_col in types["numeric"]:
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

    if not types["numeric"] and not cat_cols:
        st.info("No chartable columns were detected in this sheet.")
