from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


MISSING_THRESHOLD = 0.10
CORR_THRESHOLD = 0.70
SKEW_STD_RATIO = 0.50
TREND_MIN_POINTS = 6
TREND_MIN_ABS_PCT_PER_MONTH = 2.0
MONEY_NAME_RE = re.compile(
    r"(amount|price|revenue|sales|cost|fee|salary|income|spend|budget|profit)",
    re.I,
)


def classify_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    numeric: list[str] = []
    datetime_cols: list[str] = []
    categorical: list[str] = []
    text: list[str] = []
    identifiers: list[str] = []
    n_rows = len(df)

    for col in df.columns:
        series = df[col]
        if _looks_datetime(series):
            datetime_cols.append(col)
            continue
        non_null = series.dropna()
        if (
            n_rows >= 10
            and len(non_null) == n_rows
            and non_null.nunique(dropna=True) == n_rows
            and _looks_identifier(col, series)
        ):
            identifiers.append(col)
            continue
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            numeric.append(col)
            continue
        nunique = non_null.nunique()
        if nunique == 0:
            text.append(col)
        elif nunique <= min(30, max(10, int(len(series) * 0.05))):
            categorical.append(col)
        else:
            text.append(col)

    return {
        "numeric": numeric,
        "datetime": datetime_cols,
        "categorical": categorical,
        "text": text,
        "identifiers": identifiers,
    }


def _looks_identifier(col: str, series: pd.Series) -> bool:
    name = str(col).lower()
    if re.search(r"(^id$|_id$|uuid|guid|pk|key|code|index)", name):
        return True
    if pd.api.types.is_float_dtype(series):
        return False
    if pd.api.types.is_integer_dtype(series):
        return True
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        return True
    return False


def coerce_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def _looks_datetime(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series):
        return False
    sample = series.dropna().astype(str).head(40)
    if sample.empty:
        return False
    if sample.str.contains(r"@", regex=True).mean() > 0.3:
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() >= 0.8


def _format_number(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    abs_v = abs(value)
    if abs_v >= 1000 or (abs_v >= 1 and float(value).is_integer()):
        return f"{value:,.0f}"
    if abs_v >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _format_money_or_number(col: str, value: float) -> str:
    formatted = _format_number(value)
    if MONEY_NAME_RE.search(str(col)):
        return f"${formatted}"
    return formatted


def generate_insights(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []

    insights: list[str] = []
    n_rows = len(df)
    types = classify_columns(df)

    insights.extend(_missing_insights(df, n_rows))
    insights.extend(_duplicate_insights(df, n_rows))
    insights.extend(_outlier_insights(df, types["numeric"]))
    insights.extend(_correlation_insights(df, types["numeric"]))
    insights.extend(_trend_insights(df, types["datetime"], types["numeric"]))
    insights.extend(_skew_insights(df, types["numeric"]))
    insights.extend(_unique_id_insights(types["identifiers"]))

    return insights


def _missing_insights(df: pd.DataFrame, n_rows: int) -> list[str]:
    out = []
    if n_rows == 0:
        return out
    missing_pct = df.isna().mean()
    for col, pct in missing_pct.items():
        if pct > MISSING_THRESHOLD:
            out.append(
                f"Column '{col}' has {pct:.1%} missing values — worth cleaning before analysis."
            )
    return out


def _duplicate_insights(df: pd.DataFrame, n_rows: int) -> list[str]:
    dupes = int(df.duplicated().sum())
    if dupes > 0:
        return [
            f"Dataset contains {dupes} duplicate rows ({dupes / n_rows:.1%} of total)."
        ]
    return []


def _outlier_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[str]:
    out = []
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.size < 8:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        high = series[series > upper]
        low = series[series < lower]
        n_out = int(len(high) + len(low))
        if n_out == 0:
            continue
        if len(high) >= len(low) and len(high) > 0:
            bound = _format_money_or_number(col, float(upper))
            out.append(
                f"Detected {n_out} potential outliers in '{col}' (values above {bound})."
            )
        else:
            bound = _format_money_or_number(col, float(lower))
            out.append(
                f"Detected {n_out} potential outliers in '{col}' (values below {bound})."
            )
    return out


def _correlation_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[str]:
    if len(numeric_cols) < 2:
        return []
    corr = df[numeric_cols].apply(pd.to_numeric, errors="coerce").corr()
    out = []
    seen: set[tuple[str, str]] = set()
    for i, a in enumerate(numeric_cols):
        for b in numeric_cols[i + 1 :]:
            pair = (a, b)
            if pair in seen:
                continue
            seen.add(pair)
            value = corr.loc[a, b]
            if pd.isna(value):
                continue
            if abs(value) > CORR_THRESHOLD:
                out.append(
                    f"Strong correlation ({value:.2f}) between '{a}' and '{b}'."
                )
    return out


def _trend_insights(
    df: pd.DataFrame, datetime_cols: list[str], numeric_cols: list[str]
) -> list[str]:
    if not datetime_cols or not numeric_cols:
        return []

    date_col = datetime_cols[0]
    dates = coerce_datetime(df[date_col])
    out = []

    for num_col in numeric_cols:
        values = pd.to_numeric(df[num_col], errors="coerce")
        paired = pd.DataFrame({"date": dates, "value": values}).dropna()
        if len(paired) < TREND_MIN_POINTS:
            continue
        paired = paired.sort_values("date")
        if paired["date"].nunique() < TREND_MIN_POINTS:
            continue

        x_days = (paired["date"] - paired["date"].min()).dt.total_seconds() / 86400.0
        y = paired["value"].to_numpy(dtype=float)
        if np.allclose(y, y[0]):
            continue

        slope_per_day, _intercept = np.polyfit(x_days.to_numpy(dtype=float), y, 1)
        mean_y = float(np.mean(y))
        if mean_y == 0:
            continue
        pct_per_month = (slope_per_day * 30.437) / mean_y * 100.0
        if abs(pct_per_month) < TREND_MIN_ABS_PCT_PER_MONTH:
            continue

        direction = "UP" if pct_per_month > 0 else "DOWN"
        out.append(
            f"'{num_col}' is trending {direction} ~{abs(pct_per_month):.1f}% per month over the period."
        )
    return out


def _skew_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[str]:
    out = []
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 8:
            continue
        std = float(series.std())
        if std == 0 or np.isnan(std):
            continue
        mean = float(series.mean())
        median = float(series.median())
        ratio = (mean - median) / std
        sample_skew = float(series.skew())
        if ratio > SKEW_STD_RATIO or sample_skew > 1.0:
            out.append(
                f"Column '{col}' is heavily right-skewed (median much lower than mean)."
            )
        elif ratio < -SKEW_STD_RATIO or sample_skew < -1.0:
            out.append(
                f"Column '{col}' is heavily left-skewed (median much higher than mean)."
            )
    return out


def _unique_id_insights(identifier_cols: list[str]) -> list[str]:
    return [
        f"Column '{col}' is fully unique — likely an identifier."
        for col in identifier_cols
    ]
