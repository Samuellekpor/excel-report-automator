from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from insights import generate_insights
from profiling import categorical_profile, dataset_overview, numeric_profile

st.set_page_config(page_title="Excel Report Automator", layout="wide")

st.title("Excel Report Automator")
st.markdown(
    """
    Upload a spreadsheet and get **plain-English findings**, not just charts.

    This app reads your Excel or CSV file, profiles the columns, flags issues
    an analyst would notice (missing values, duplicates, outliers, odd trends),
    and packages the story into a downloadable Excel and PDF report.
    """
)


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
    st.markdown("## 📌 Key Insights")
    if not insights:
        st.success("No notable issues detected — this dataset looks clean.")
        return
    for i, sentence in enumerate(insights, start=1):
        st.markdown(f"{i}. {sentence}")


def render_profiling(df: pd.DataFrame) -> None:
    overview = dataset_overview(df)
    types = overview["types"]
    st.markdown("## Dataset profile")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{overview['rows']:,}")
    c2.metric("Columns", f"{overview['columns']:,}")
    c3.metric("Duplicate rows", f"{overview['duplicate_rows']:,}")
    c4.metric("Missing cells", f"{overview['missing_pct']:.1f}%")

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


uploaded = st.file_uploader(
    "Upload an Excel or CSV file",
    type=["xlsx", "xls", "csv"],
    help="Accepted formats: .xlsx, .xls, .csv",
)

if uploaded is None:
    st.info("Start by uploading a spreadsheet. You'll see a preview of the first 100 rows.")
else:
    df, error = load_uploaded_file(uploaded)
    if error:
        st.error(error)
    elif df is None or df.empty:
        st.error("This file is empty — there are no rows to analyze.")
    else:
        render_insights(generate_insights(df))
        render_profiling(df)
        st.subheader("Preview")
        st.caption(f"Showing the first {min(100, len(df)):,} of {len(df):,} rows.")
        st.dataframe(df.head(100), use_container_width=True)
