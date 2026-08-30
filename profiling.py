from __future__ import annotations

import pandas as pd

from insights import classify_columns, coerce_datetime


def dataset_overview(df: pd.DataFrame) -> dict:
    n_rows, n_cols = df.shape
    duplicate_rows = int(df.duplicated().sum())
    total_cells = n_rows * n_cols
    missing_cells = int(df.isna().sum().sum())
    missing_pct = (missing_cells / total_cells * 100.0) if total_cells else 0.0
    types = classify_columns(df)
    return {
        "rows": n_rows,
        "columns": n_cols,
        "duplicate_rows": duplicate_rows,
        "missing_cells": missing_cells,
        "missing_pct": missing_pct,
        "types": types,
    }


def numeric_profile(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in numeric_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        rows.append(
            {
                "Column": col,
                "Count": int(s.count()),
                "Mean": s.mean(),
                "Median": s.median(),
                "Min": s.min(),
                "Max": s.max(),
                "Std": s.std(),
                "Missing": int(s.isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def categorical_profile(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    profiles = []
    for col in cols:
        s = df[col]
        vc = s.dropna().astype(str).value_counts().head(5)
        profiles.append(
            {
                "column": col,
                "unique_count": int(s.nunique(dropna=True)),
                "missing": int(s.isna().sum()),
                "top_values": pd.DataFrame(
                    {"Value": vc.index.astype(str), "Count": vc.values}
                ),
            }
        )
    return profiles


def typed_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with datetime columns parsed for downstream charts."""
    out = df.copy()
    types = classify_columns(out)
    for col in types["datetime"]:
        out[col] = coerce_datetime(out[col])
    return out
