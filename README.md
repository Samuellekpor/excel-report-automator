# Excel Report Automator

Upload any Excel (`.xlsx` / `.xls`) or CSV file and get a report an analyst would actually write:

- automatic data profiling
- **plain-English insights** (missing data, duplicates, outliers, correlations, trends, and more)
- charts
- a downloadable Excel workbook and PDF

No external AI API is required. Insights are generated from the data with deterministic rules.

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually http://localhost:8501), upload a spreadsheet, and generate a report.
