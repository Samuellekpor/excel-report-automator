from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from charts import render_charts
from insights import generate_findings, rank_findings, supporting_findings
from profiling import categorical_profile, dataset_overview, numeric_profile
from reports import build_reports
from ui import (
    bento_metrics,
    cleaning_nudge,
    hero,
    inject_theme,
    insight_cards,
    section_header,
    sidebar_chrome,
)

SAMPLE_PATH = Path(__file__).with_name("sample_sales.csv")


@st.cache_data(show_spinner=False)
def cached_generate_findings(df: pd.DataFrame):
    return generate_findings(df)


@st.cache_data(show_spinner=False)
def cached_dataset_overview(df: pd.DataFrame):
    return dataset_overview(df)


@st.cache_data(show_spinner=False)
def cached_build_reports(df: pd.DataFrame, source_name: str, kind: str):
    return build_reports(df, source_name, kind=kind)


st.set_page_config(
    page_title="Excel Report Automator",
    layout="wide",
    # Open on desktop; collapse on narrow viewports so the sidebar does not cover the hero.
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

            selected = st.selectbox("Which sheet should we use?", sheets, index=0)
            df = excel_file.parse(selected)
            return df, None

        return None, f"This file type is not supported: .{suffix}"
    except Exception as exc:
        return None, f"We could not read this file. {exc}"


def render_insights(df: pd.DataFrame) -> None:
    all_findings = cached_generate_findings(df)
    briefing = rank_findings(all_findings)
    extra = supporting_findings(all_findings, briefing)
    section_header(
        "01  ·  Briefing",
        "What matters",
        "Watch first — those items can skew the rest. Then read Explain for the pattern. Ignore is noise.",
    )
    cleaning_nudge(all_findings)
    insight_cards(briefing)
    if extra:
        with st.expander(f"Also noted ({len(extra)}) — lower priority"):
            insight_cards(extra)


def render_profiling(df: pd.DataFrame) -> None:
    overview = cached_dataset_overview(df)
    types = overview["types"]
    section_header(
        "02  ·  Profile",
        "What's in this sheet",
        "Row counts, empty cells, and a look at each column.",
    )
    bento_metrics(
        overview["rows"],
        overview["columns"],
        overview["duplicate_rows"],
        overview["missing_pct"],
    )

    overview_tab, numeric_tab, category_tab, types_tab = st.tabs(
        ["Overview", "Numbers", "Categories & text", "Column types"]
    )

    with overview_tab:
        st.write(
            {
                "Rows": overview["rows"],
                "Columns": overview["columns"],
                "Duplicate rows": overview["duplicate_rows"],
                "Missing cells": overview["missing_cells"],
                "Empty cells": f"{overview['missing_pct']:.1f}%",
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
            st.info("No number columns in this sheet.")

    with category_tab:
        cat_cols = types["categorical"] + types["text"] + types["identifiers"]
        if not cat_cols:
            st.info("No category or text columns in this sheet.")
        else:
            for profile in categorical_profile(df, cat_cols):
                st.markdown(f"**{profile['column']}**")
                st.caption(
                    f"{profile['unique_count']:,} distinct values · {profile['missing']:,} empty"
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
    kind = st.session_state.get("report_kind", "full")
    suffix = "executive" if kind == "executive" else "full"
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download Excel",
            data=excel_bytes,
            file_name=f"{stem}_{suffix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{stem}_{suffix}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


def render_workspace(df: pd.DataFrame, source_name: str) -> None:
    render_insights(df)
    render_profiling(df)
    render_charts(df)

    section_header(
        "04  ·  Report",
        "Excel and PDF",
        "Executive is a short three-page briefing. Full adds the extra charts.",
    )
    kind_label = st.radio(
        "How long should the report be?",
        ["Executive (3 pages)", "Full report"],
        horizontal=True,
    )
    report_kind = "executive" if kind_label.startswith("Executive") else "full"
    if st.button("Generate report", type="primary"):
        with st.spinner("Building Excel and PDF…"):
            excel_bytes, pdf_bytes = cached_build_reports(df, source_name, report_kind)
        st.session_state["excel_report"] = excel_bytes
        st.session_state["pdf_report"] = pdf_bytes
        st.session_state["report_stem"] = source_name.rsplit(".", 1)[0]
        st.session_state["report_kind"] = report_kind
        st.success(
            f"Ready to download — Excel {len(excel_bytes) / 1024:.1f} KB, "
            f"PDF {len(pdf_bytes) / 1024:.1f} KB."
        )
    render_downloads()

    section_header(
        "05  ·  Preview",
        "Check the import",
        f"First {min(100, len(df)):,} of {len(df):,} rows — confirm we read the file correctly.",
    )
    st.dataframe(df.head(100), use_container_width=True)


section_header(
    "Start here",
    "Upload a file",
    "Excel (.xlsx, .xls) or CSV. If the workbook has several sheets, pick one after you upload.",
)

uploaded = st.file_uploader(
    "Upload an Excel or CSV file",
    type=["xlsx", "xls", "csv"],
    help="Accepted formats: .xlsx, .xls, .csv",
    label_visibility="collapsed",
)

if uploaded is not None:
    st.session_state["use_sample"] = False
    df, error = load_uploaded_file(uploaded)
    if error:
        st.error(error)
    elif df is None or df.empty:
        st.error("This file is empty — there are no rows to analyze.")
    else:
        render_workspace(df, uploaded.name)
elif st.session_state.get("use_sample"):
    render_workspace(pd.read_csv(SAMPLE_PATH), SAMPLE_PATH.name)
    if st.button("Back to upload"):
        st.session_state["use_sample"] = False
        st.rerun()
else:
    st.info("Upload a spreadsheet, or try the sample to see a briefing in one click.")
    if st.button("Try with sample data", type="primary"):
        st.session_state["use_sample"] = True
        st.rerun()
