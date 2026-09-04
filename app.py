from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from charts import render_charts
from insights import generate_insights
from profiling import categorical_profile, dataset_overview, numeric_profile
from reports import build_reports
from ui import (
    bento_metrics,
    hero,
    inject_theme,
    insight_cards,
    section_header,
    sidebar_chrome,
)

st.set_page_config(
    page_title="Excel Report Automator",
    layout="wide",
    # Open on desktop; collapse on narrow viewports so Protocol does not cover the hero.
    initial_sidebar_state="auto",
)

inject_theme()

with st.sidebar:
    sidebar_chrome()

hero()


def _file_suffix(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame | None, str | None]:
    """Read CSV or Excel. Returns (dataframe, error_message)."""
    name = uploaded_file.name
    suffix = _file_suffix(name)
    raw = uploaded_file.getvalue()

    try:
        if suffix == "csv":
            df = pd.read_csv(BytesIO(raw))
            return df, None

        if suffix in {"xlsx", "xls"}:
            engine = "openpyxl" if suffix == "xlsx" else "xlrd"
            excel_file = pd.ExcelFile(BytesIO(raw), engine=engine)
            sheets = excel_file.sheet_names
            if not sheets:
                return None, "This workbook has no sheets to read."

            selected = st.selectbox("Select a sheet", sheets, index=0)
            df = excel_file.parse(selected)
            return df, None

        return None, f"Unsupported file type: .{suffix}"
    except Exception as exc:
        return None, f"Could not read this file. {exc}"


def render_insights(insights: list[str]) -> None:
    section_header(
        "01  ·  Briefing",
        "Key Insights",
        "What a report analyst would flag before building slides.",
    )
    insight_cards(insights)


def render_profiling(df: pd.DataFrame) -> None:
    overview = dataset_overview(df)
    types = overview["types"]
    section_header(
        "02  ·  Structure",
        "Dataset profile",
        "Shape, quality, and column-level stats for the selected sheet.",
    )
    bento_metrics(
        overview["rows"],
        overview["columns"],
        overview["duplicate_rows"],
        overview["missing_pct"],
    )

    overview_tab, numeric_tab, category_tab, types_tab = st.tabs(
        ["Overview", "Numeric", "Categorical / text", "Column types"]
    )

    with overview_tab:
        st.write(
            {
                "Rows": overview["rows"],
                "Columns": overview["columns"],
                "Duplicate rows": overview["duplicate_rows"],
                "Missing cells": overview["missing_cells"],
                "Missing overall": f"{overview['missing_pct']:.1f}%",
            }
        )

    with numeric_tab:
        if types["numeric"]:
            stats = numeric_profile(df, types["numeric"])
            st.dataframe(
                stats.style.format(
                    {
                        "Mean": "{:,.2f}",
                        "Median": "{:,.2f}",
                        "Min": "{:,.2f}",
                        "Max": "{:,.2f}",
                        "Std": "{:,.2f}",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.info("No numeric columns detected.")

    with category_tab:
        cat_cols = types["categorical"] + types["text"] + types["identifiers"]
        if not cat_cols:
            st.info("No categorical or text columns detected.")
        else:
            for profile in categorical_profile(df, cat_cols):
                st.markdown(f"**{profile['column']}**")
                st.caption(
                    f"{profile['unique_count']:,} unique values · {profile['missing']:,} missing"
                )
                st.dataframe(profile["top_values"], use_container_width=True, hide_index=True)

    with types_tab:
        type_rows = []
        for kind, cols in types.items():
            for col in cols:
                type_rows.append({"Column": col, "Detected type": kind})
        st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)


def render_downloads() -> None:
    excel_bytes = st.session_state.get("excel_report")
    pdf_bytes = st.session_state.get("pdf_report")
    if not excel_bytes or not pdf_bytes:
        return
    stem = st.session_state.get("report_stem", "report")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download Excel  ↗",
            data=excel_bytes,
            file_name=f"{stem}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Download PDF  ↗",
            data=pdf_bytes,
            file_name=f"{stem}_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


section_header(
    "Drop the source",
    "Upload your file",
    "Excel (.xlsx, .xls) or CSV. For workbooks, choose the sheet to analyze.",
)

uploaded = st.file_uploader(
    "Upload an Excel or CSV file",
    type=["xlsx", "xls", "csv"],
    help="Accepted formats: .xlsx, .xls, .csv",
    label_visibility="collapsed",
)

if uploaded is None:
    st.info("Start by uploading a spreadsheet. Insights, profile, charts, and the briefing files appear here.")
else:
    df, error = load_uploaded_file(uploaded)
    if error:
        st.error(error)
    elif df is None or df.empty:
        st.error("This file is empty — there are no rows to analyze.")
    else:
        render_insights(generate_insights(df))
        render_profiling(df)
        render_charts(df)

        section_header(
            "04  ·  Deliverable",
            "Generate report",
            "A formatted Excel workbook and a PDF briefing from the current sheet.",
        )
        if st.button("Generate Report", type="primary"):
            with st.spinner("Writing Excel and PDF reports…"):
                excel_bytes, pdf_bytes = build_reports(df, uploaded.name)
            st.session_state["excel_report"] = excel_bytes
            st.session_state["pdf_report"] = pdf_bytes
            st.session_state["report_stem"] = uploaded.name.rsplit(".", 1)[0]
            st.success(
                f"Report ready — Excel {len(excel_bytes) / 1024:.1f} KB, "
                f"PDF {len(pdf_bytes) / 1024:.1f} KB."
            )
        render_downloads()

        section_header(
            "05  ·  Receipt",
            "Data preview",
            f"First {min(100, len(df)):,} of {len(df):,} rows — sanity-check the import.",
        )
        st.dataframe(df.head(100), use_container_width=True)
