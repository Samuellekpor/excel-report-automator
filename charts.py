from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insights import classify_columns, coerce_datetime


def render_charts(df: pd.DataFrame) -> None:
    st.markdown("## Charts")
    types = classify_columns(df)

    if types["numeric"]:
        st.markdown("### Numeric distributions")
        for col in types["numeric"]:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            fig = px.histogram(series, x=series.name or col, nbins=30, title=f"Histogram — {col}")
            fig.update_layout(xaxis_title=col, yaxis_title="Count", bargap=0.05)
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
            st.plotly_chart(fig, use_container_width=True)

    if len(types["numeric"]) >= 2:
        st.markdown("### Correlation heatmap")
        corr = df[types["numeric"]].apply(pd.to_numeric, errors="coerce").corr()
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=list(corr.columns),
                y=list(corr.index),
                colorscale="RdBu",
                zmid=0,
                zmin=-1,
                zmax=1,
                colorbar=dict(title="corr"),
            )
        )
        fig.update_layout(title="Numeric correlation")
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
            fig.update_layout(xaxis_title=date_col, yaxis_title=num_col)
            st.plotly_chart(fig, use_container_width=True)

    if not types["numeric"] and not cat_cols:
        st.info("No chartable columns were detected in this sheet.")
