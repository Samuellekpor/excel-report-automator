from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Lane = Literal["watch", "explain", "ignore"]


@dataclass(frozen=True)
class Finding:
    lane: Lane
    sentence: str
    so_what: str
    score: float
    kind: str


def _finding(
    lane: Lane, sentence: str, so_what: str, score: float, kind: str
) -> Finding:
    return Finding(lane=lane, sentence=sentence, so_what=so_what, score=score, kind=kind)


MISSING_THRESHOLD = 0.10
CORR_THRESHOLD = 0.70
SKEW_STD_RATIO = 0.50
TREND_MIN_POINTS = 6
TREND_MIN_ABS_PCT_PER_MONTH = 2.0
BRIEFING_LIMIT = 7
SEGMENT_MIN_RATIO = 1.5
SEGMENT_MAX_GROUPS = 12
SEGMENT_MIN_PER_GROUP = 2
PERIOD_MIN_ABS_PCT = 8.0
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
    if sample.str.contains(r"\d", regex=True).mean() < 0.6:
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


def generate_findings(df: pd.DataFrame) -> list[Finding]:
    if df is None or df.empty:
        return []

    n_rows = len(df)
    types = classify_columns(df)
    findings: list[Finding] = []
    findings.extend(_missing_insights(df, n_rows))
    findings.extend(_duplicate_insights(df, n_rows))
    findings.extend(_outlier_insights(df, types["numeric"]))
    findings.extend(_correlation_insights(df, types["numeric"]))
    findings.extend(_trend_insights(df, types["datetime"], types["numeric"]))
    findings.extend(_skew_insights(df, types["numeric"]))
    findings.extend(_segment_insights(df, types["categorical"], types["numeric"]))
    findings.extend(_period_insights(df, types["datetime"], types["numeric"]))
    findings.extend(_unique_id_insights(types["identifiers"]))
    return findings


def generate_insights(df: pd.DataFrame) -> list[str]:
    return [item.sentence for item in rank_findings(generate_findings(df))]


def rank_findings(
    findings: list[Finding], limit: int = BRIEFING_LIMIT
) -> list[Finding]:
    """Keep Watch/Explain, drop Ignore from the lead list, then take the top scores."""
    story = [item for item in findings if item.lane != "ignore"]
    ranked = sorted(story, key=lambda item: (-item.score, item.kind, item.sentence))
    return ranked[:limit]


def supporting_findings(
    findings: list[Finding], briefing: list[Finding]
) -> list[Finding]:
    chosen = set(briefing)
    rest = [item for item in findings if item not in chosen]
    return sorted(rest, key=lambda item: (-item.score, item.sentence))


def _missing_insights(df: pd.DataFrame, n_rows: int) -> list[Finding]:
    out: list[Finding] = []
    if n_rows == 0:
        return out
    missing_pct = df.isna().mean()
    for col, pct in missing_pct.items():
        if pct > MISSING_THRESHOLD:
            out.append(
                _finding(
                    "watch",
                    f"Column '{col}' has {pct:.1%} missing values — worth cleaning before analysis.",
                    "Those gaps can quietly shrink averages and hide the true mix.",
                    40 + float(pct) * 80,
                    "missing",
                )
            )
    return out


def _duplicate_insights(df: pd.DataFrame, n_rows: int) -> list[Finding]:
    dupes = int(df.duplicated().sum())
    if dupes <= 0:
        return []
    share = dupes / n_rows
    return [
        _finding(
            "watch",
            f"Dataset contains {dupes} duplicate rows ({share:.1%} of total).",
            "Repeated rows will double-count totals until they are removed.",
            38 + share * 80,
            "duplicate",
        )
    ]


def _outlier_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[Finding]:
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
            sentence = f"Detected {n_out} potential outliers in '{col}' (values above {bound})."
        else:
            bound = _format_money_or_number(col, float(lower))
            sentence = f"Detected {n_out} potential outliers in '{col}' (values below {bound})."
        out.append(
            _finding(
                "watch",
                sentence,
                "A few extreme values may be driving the mean more than the typical row.",
                32 + min(n_out, 25),
                "outlier",
            )
        )
    return out


def _correlation_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[Finding]:
    if len(numeric_cols) < 2:
        return []
    corr = df[numeric_cols].apply(pd.to_numeric, errors="coerce").corr()
    out: list[Finding] = []
    for i, a in enumerate(numeric_cols):
        for b in numeric_cols[i + 1 :]:
            value = corr.loc[a, b]
            if pd.isna(value) or abs(value) <= CORR_THRESHOLD:
                continue
            if value < 0:
                so_what = "When one rises the other tends to fall — a trade-off, not two independent facts."
            else:
                so_what = "These two move together — treat them as one story, not two separate ones."
            out.append(
                _finding(
                    "explain",
                    f"Strong correlation ({value:.2f}) between '{a}' and '{b}'.",
                    so_what,
                    48 + abs(float(value)) * 25,
                    "correlation",
                )
            )
    return out


def _trend_insights(
    df: pd.DataFrame, datetime_cols: list[str], numeric_cols: list[str]
) -> list[Finding]:
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
            _finding(
                "explain",
                f"'{num_col}' is trending {direction} ~{abs(pct_per_month):.1f}% per month over the period.",
                "If this continues, run-rate will look very different from the period average.",
                52 + min(abs(pct_per_month), 40),
                "trend",
            )
        )
    return out


def _skew_insights(df: pd.DataFrame, numeric_cols: list[str]) -> list[Finding]:
    out: list[Finding] = []
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
            sentence = f"Column '{col}' is heavily right-skewed (median much lower than mean)."
        elif ratio < -SKEW_STD_RATIO or sample_skew < -1.0:
            sentence = f"Column '{col}' is heavily left-skewed (median much higher than mean)."
        else:
            continue
        out.append(
            _finding(
                "explain",
                sentence,
                "The typical row is not the average — medians will tell a different story than totals.",
                22 + min(abs(sample_skew), 8) * 2,
                "skew",
            )
        )
    return out


def _hero_numeric(numeric_cols: list[str]) -> str | None:
    if not numeric_cols:
        return None
    money = [col for col in numeric_cols if MONEY_NAME_RE.search(str(col))]
    preferred = ("revenue", "sales", "amount")
    for needle in preferred:
        for col in money:
            if needle in str(col).lower():
                return col
    if money:
        return money[0]
    return numeric_cols[0]


def _segment_insights(
    df: pd.DataFrame, categorical_cols: list[str], numeric_cols: list[str]
) -> list[Finding]:
    hero = _hero_numeric(numeric_cols)
    if not hero or not categorical_cols:
        return []
    values = pd.to_numeric(df[hero], errors="coerce")
    candidates: list[Finding] = []
    for cat in categorical_cols:
        frame = pd.DataFrame({"group": df[cat].astype(str), "value": values}).dropna()
        counts = frame["group"].value_counts()
        keep = counts[counts >= SEGMENT_MIN_PER_GROUP].index
        means = frame[frame["group"].isin(keep)].groupby("group")["value"].mean()
        if len(means) < 2 or len(means) > SEGMENT_MAX_GROUPS:
            continue
        top_name = str(means.idxmax())
        bot_name = str(means.idxmin())
        if top_name == bot_name:
            continue
        top_val = float(means.max())
        bot_val = float(means.min())
        if bot_val == 0:
            if top_val <= 0:
                continue
            sentence = (
                f"'{top_name}' leads '{cat}' on '{hero}' "
                f"({_format_money_or_number(hero, top_val)} avg) versus '{bot_name}' near zero."
            )
            ratio = 3.0
        else:
            ratio = top_val / bot_val
            if ratio < SEGMENT_MIN_RATIO:
                continue
            sentence = f"'{top_name}' is {ratio:.1f}× '{bot_name}' on '{hero}'."
        candidates.append(
            _finding(
                "explain",
                sentence,
                "The mix is doing more work than the overall average suggests — slice before you conclude.",
                58 + min(ratio * 4, 24),
                "segment",
            )
        )
    candidates.sort(key=lambda item: -item.score)
    return candidates[:2]


def _period_insights(
    df: pd.DataFrame, datetime_cols: list[str], numeric_cols: list[str]
) -> list[Finding]:
    if not datetime_cols:
        return []
    hero = _hero_numeric(numeric_cols)
    if not hero:
        return []
    dates = coerce_datetime(df[datetime_cols[0]])
    values = pd.to_numeric(df[hero], errors="coerce")
    paired = pd.DataFrame({"date": dates, "value": values}).dropna().sort_values("date")
    if paired["date"].nunique() < 6:
        return []

    span_days = (paired["date"].max() - paired["date"].min()).days
    if span_days >= 60:
        mid = paired["date"].min() + (paired["date"].max() - paired["date"].min()) / 2
        first = paired.loc[paired["date"] < mid, "value"].mean()
        second = paired.loc[paired["date"] >= mid, "value"].mean()
        earlier, later = "the first half of the period", "the second half"
    else:
        cut = len(paired) // 2
        first = paired["value"].iloc[:cut].mean()
        second = paired["value"].iloc[cut:].mean()
        earlier, later = "the earlier rows", "the later rows"

    if pd.isna(first) or pd.isna(second) or first == 0:
        return []
    pct = (float(second) - float(first)) / abs(float(first)) * 100.0
    if abs(pct) < PERIOD_MIN_ABS_PCT:
        return []
    direction = "up" if pct > 0 else "down"
    return [
        _finding(
            "explain",
            f"'{hero}' is {direction} {abs(pct):.0f}% in {later} versus {earlier}.",
            "The period average hides a shift — compare the two windows before you lock a target.",
            60 + min(abs(pct), 30),
            "period",
        )
    ]


def _unique_id_insights(identifier_cols: list[str]) -> list[Finding]:
    return [
        _finding(
            "ignore",
            f"Column '{col}' is fully unique — likely an identifier.",
            "Useful as a key, but it should not be charted as a measure.",
            6.0,
            "identifier",
        )
        for col in identifier_cols
    ]
