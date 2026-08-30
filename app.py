from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

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
        st.subheader("Preview")
        st.caption(f"Showing the first {min(100, len(df)):,} of {len(df):,} rows.")
        st.dataframe(df.head(100), use_container_width=True)
