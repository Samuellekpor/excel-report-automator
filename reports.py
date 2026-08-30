from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from insights import classify_columns, coerce_datetime, generate_insights
from profiling import categorical_profile, dataset_overview, numeric_profile

NAVY = "#1B3A4B"
TEAL = "#0E7C7B"
GOLD = "#C9A227"
LIGHT = "#F4F7F8"


def build_reports(df: pd.DataFrame, source_name: str) -> tuple[bytes, bytes]:
    insights = generate_insights(df)
    overview = dataset_overview(df)
    types = overview["types"]
    generated_at = datetime.now()
    chart_images = _chart_images(df, types)
    excel_bytes = _build_excel(
        df, source_name, generated_at, insights, overview, types, chart_images
    )
    pdf_bytes = _build_pdf(
        df, source_name, generated_at, insights, overview, types, chart_images
    )
    return excel_bytes, pdf_bytes


def _excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce").astype(str).replace("NaT", "")
        elif out[col].dtype == "object":
            out[col] = out[col].apply(lambda v: "" if pd.isna(v) else str(v))
    return out


def _chart_images(df: pd.DataFrame, types: dict[str, list[str]]) -> list[tuple[str, bytes]]:
    images: list[tuple[str, bytes]] = []

    for col in types["numeric"]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.hist(series, bins=30, color=TEAL, edgecolor="white")
        ax.set_title(f"Histogram — {col}", color=NAVY, loc="left")
        ax.set_xlabel(col)
        ax.set_ylabel("Count")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        images.append((f"hist_{col}", _fig_to_png(fig)))

    cat_cols = types["categorical"][:8]
    for col in cat_cols:
        counts = df[col].dropna().astype(str).value_counts().head(10)
        if counts.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.bar(counts.index.astype(str), counts.values, color=NAVY)
        ax.set_title(f"Top values — {col}", color=NAVY, loc="left")
        ax.tick_params(axis="x", rotation=35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        images.append((f"bar_{col}", _fig_to_png(fig)))

    if len(types["numeric"]) >= 2:
        corr = df[types["numeric"]].apply(pd.to_numeric, errors="coerce").corr()
        fig, ax = plt.subplots(figsize=(6.5, 5.2))
        im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.index)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.index)
        ax.set_title("Correlation heatmap", color=NAVY, loc="left")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        images.append(("corr_heatmap", _fig_to_png(fig)))

    if types["datetime"] and types["numeric"]:
        date_col = types["datetime"][0]
        dates = coerce_datetime(df[date_col])
        for num_col in types["numeric"][:4]:
            paired = pd.DataFrame(
                {"date": dates, "value": pd.to_numeric(df[num_col], errors="coerce")}
            ).dropna()
            if paired.empty or paired["date"].nunique() < 2:
                continue
            paired = paired.sort_values("date").groupby("date", as_index=False)["value"].mean()
            fig, ax = plt.subplots(figsize=(7.2, 3.6))
            ax.plot(paired["date"], paired["value"], color=TEAL, linewidth=2)
            ax.set_title(f"{num_col} over time", color=NAVY, loc="left")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.autofmt_xdate()
            images.append((f"ts_{num_col}", _fig_to_png(fig)))

    return images


def _fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _build_excel(
    df: pd.DataFrame,
    source_name: str,
    generated_at: datetime,
    insights: list[str],
    overview: dict[str, Any],
    types: dict[str, list[str]],
    chart_images: list[tuple[str, bytes]],
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 18, "font_color": NAVY, "font_name": "Calibri"}
        )
        subtitle_fmt = workbook.add_format(
            {"font_size": 11, "font_color": TEAL, "font_name": "Calibri"}
        )
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": NAVY,
                "font_color": "white",
                "border": 0,
                "font_name": "Calibri",
            }
        )
        label_fmt = workbook.add_format({"bold": True, "font_name": "Calibri", "font_color": NAVY})
        cell_fmt = workbook.add_format({"font_name": "Calibri"})
        wrap_fmt = workbook.add_format({"font_name": "Calibri", "text_wrap": True, "valign": "top"})
        insight_fmt = workbook.add_format(
            {"font_name": "Calibri", "text_wrap": True, "bg_color": LIGHT, "valign": "top"}
        )

        summary = workbook.add_worksheet("Summary")
        writer.sheets["Summary"] = summary
        summary.set_column("A:A", 28)
        summary.set_column("B:B", 88)
        summary.write("A1", "Excel Report Automator", title_fmt)
        summary.write("A2", f"Source: {source_name}", subtitle_fmt)
        summary.write("A3", f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M')}", subtitle_fmt)

        summary.write("A5", "Overview", header_fmt)
        summary.write("B5", "", header_fmt)
        metrics = [
            ("Rows", f"{overview['rows']:,}"),
            ("Columns", f"{overview['columns']:,}"),
            ("Duplicate rows", f"{overview['duplicate_rows']:,}"),
            ("Missing cells", f"{overview['missing_cells']:,}"),
            ("Missing overall", f"{overview['missing_pct']:.1f}%"),
        ]
        for i, (label, value) in enumerate(metrics):
            summary.write(5 + i, 0, label, label_fmt)
            summary.write(5 + i, 1, value, cell_fmt)

        start = 12
        summary.write(start, 0, "Key Insights", header_fmt)
        summary.write(start, 1, "", header_fmt)
        if not insights:
            summary.write(start + 1, 0, "No notable issues detected — this dataset looks clean.", insight_fmt)
            summary.write(start + 1, 1, "", insight_fmt)
            summary.set_row(start + 1, 28)
        else:
            for i, sentence in enumerate(insights):
                summary.write(start + 1 + i, 0, f"{i + 1}.", label_fmt)
                summary.write(start + 1 + i, 1, sentence, insight_fmt)
                summary.set_row(start + 1 + i, 28)

        type_rows = []
        for kind, cols in types.items():
            for col in cols:
                type_rows.append({"Column": col, "Detected type": kind})
        pd.DataFrame(type_rows).to_excel(writer, sheet_name="Column Types", index=False)

        num_df = numeric_profile(df, types["numeric"]) if types["numeric"] else pd.DataFrame()
        if not num_df.empty:
            num_df.to_excel(writer, sheet_name="Numeric Stats", index=False)

        cat_rows = []
        cat_cols = types["categorical"] + types["text"] + types["identifiers"]
        for profile in categorical_profile(df, cat_cols):
            top = "; ".join(
                f"{row.Value} ({row.Count})" for row in profile["top_values"].itertuples()
            )
            cat_rows.append(
                {
                    "Column": profile["column"],
                    "Unique": profile["unique_count"],
                    "Missing": profile["missing"],
                    "Top values": top,
                }
            )
        if cat_rows:
            pd.DataFrame(cat_rows).to_excel(writer, sheet_name="Category Stats", index=False)

        _excel_safe(df).to_excel(writer, sheet_name="Data", index=False)

        for sheet_name in writer.sheets:
            if sheet_name == "Summary":
                continue
            ws = writer.sheets[sheet_name]
            ws.set_row(0, 20, header_fmt)
            ws.freeze_panes(1, 0)
            ws.set_column("A:Z", 18)

        charts_ws = workbook.add_worksheet("Charts")
        writer.sheets["Charts"] = charts_ws
        charts_ws.write("A1", "Charts", title_fmt)
        row = 2
        for name, png in chart_images:
            charts_ws.write(row, 0, name.replace("_", " "), label_fmt)
            charts_ws.insert_image(
                row + 1,
                0,
                f"{name}.png",
                {"image_data": BytesIO(png), "x_scale": 0.9, "y_scale": 0.9},
            )
            row += 20

    return output.getvalue()


def _build_pdf(
    df: pd.DataFrame,
    source_name: str,
    generated_at: datetime,
    insights: list[str],
    overview: dict[str, Any],
    types: dict[str, list[str]],
    chart_images: list[tuple[str, bytes]],
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"Excel Report Automator — {source_name}",
    )
    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=26,
        textColor=colors.HexColor(NAVY),
        alignment=TA_CENTER,
        spaceAfter=16,
    )
    cover_sub = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=12,
        textColor=colors.HexColor(TEAL),
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    h1 = ParagraphStyle(
        "H1Custom",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        textColor=colors.HexColor(NAVY),
        fontSize=16,
        spaceBefore=12,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        leading=15,
        alignment=TA_LEFT,
    )

    story = []
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph("Excel Report Automator", cover_title))
    story.append(Paragraph("Analyst briefing", cover_sub))
    story.append(Paragraph(source_name, cover_sub))
    story.append(Paragraph(generated_at.strftime("%B %d, %Y · %H:%M"), cover_sub))
    story.append(PageBreak())

    story.append(Paragraph("Key Insights", h1))
    if not insights:
        story.append(
            Paragraph("No notable issues detected — this dataset looks clean.", body)
        )
    else:
        for i, sentence in enumerate(insights, start=1):
            story.append(Paragraph(f"{i}. {sentence}", body))
            story.append(Spacer(1, 6))

    story.append(Paragraph("Dataset overview", h1))
    overview_table = Table(
        [
            ["Metric", "Value"],
            ["Rows", f"{overview['rows']:,}"],
            ["Columns", f"{overview['columns']:,}"],
            ["Duplicate rows", f"{overview['duplicate_rows']:,}"],
            ["Missing cells", f"{overview['missing_cells']:,}"],
            ["Missing overall", f"{overview['missing_pct']:.1f}%"],
        ],
        colWidths=[2.4 * inch, 4.2 * inch],
    )
    overview_table.setStyle(_table_style())
    story.append(overview_table)

    if types["numeric"]:
        story.append(Paragraph("Numeric statistics", h1))
        num_df = numeric_profile(df, types["numeric"])
        header = ["Column", "Count", "Mean", "Median", "Min", "Max", "Std", "Missing"]
        rows = [header]
        for rec in num_df.to_dict("records"):
            rows.append(
                [
                    str(rec["Column"]),
                    f"{rec['Count']:,}",
                    _n(rec["Mean"]),
                    _n(rec["Median"]),
                    _n(rec["Min"]),
                    _n(rec["Max"]),
                    _n(rec["Std"]),
                    f"{rec['Missing']:,}",
                ]
            )
        table = Table(rows, repeatRows=1)
        table.setStyle(_table_style())
        story.append(table)

    cat_cols = types["categorical"] + types["text"] + types["identifiers"]
    if cat_cols:
        story.append(Paragraph("Categorical and text columns", h1))
        cat_header = ["Column", "Unique", "Missing", "Top values"]
        cat_rows = [cat_header]
        for profile in categorical_profile(df, cat_cols):
            top = ", ".join(
                f"{row.Value} ({row.Count})" for row in profile["top_values"].itertuples()
            )
            cat_rows.append(
                [
                    Paragraph(str(profile["column"]), body),
                    str(profile["unique_count"]),
                    str(profile["missing"]),
                    Paragraph(top or "—", body),
                ]
            )
        cat_table = Table(cat_rows, colWidths=[1.4 * inch, 0.8 * inch, 0.9 * inch, 3.5 * inch], repeatRows=1)
        cat_table.setStyle(_table_style())
        story.append(cat_table)

    if chart_images:
        story.append(PageBreak())
        story.append(Paragraph("Charts", h1))
        for name, png in chart_images:
            story.append(Paragraph(name.replace("_", " "), body))
            img = Image(BytesIO(png))
            img._restrictSize(6.8 * inch, 3.8 * inch)
            story.append(img)
            story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()


def _n(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.2f}"


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor(LIGHT)),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D0D7DA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )
