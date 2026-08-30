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
