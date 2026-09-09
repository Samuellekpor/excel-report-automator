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

from insights import Finding, classify_columns, coerce_datetime, generate_findings, rank_findings, supporting_findings
from profiling import categorical_profile, dataset_overview, numeric_profile

INK = "#0A0A0C"
CREAM = "#F3F1EC"
TEAL = "#0F766E"
TEAL_BRIGHT = "#5EEAD4"
VIOLET = "#6D28D9"
VIOLET_SOFT = "#C4B5FD"
MUTED = "#5C6568"
HAIR = "#D6D1C7"
LIGHT = "#F3F1EC"

CORR_CMAP = [
    (0.0, "#0F766E"),
    (0.25, "#5EEAD4"),
    (0.5, "#F3F1EC"),
    (0.75, "#C4B5FD"),
    (1.0, "#6D28D9"),
]


def build_reports(df: pd.DataFrame, source_name: str) -> tuple[bytes, bytes]:
    all_findings = generate_findings(df)
    briefing = rank_findings(all_findings)
    extra = supporting_findings(all_findings, briefing)
    overview = dataset_overview(df)
    types = overview["types"]
    generated_at = datetime.now()
    context = report_context(df, source_name, generated_at, overview, types)
    chart_images = _chart_images(df, types)
    excel_bytes = _build_excel(
        df, context, briefing, extra, overview, types, chart_images
    )
    pdf_bytes = _build_pdf(
        df, context, briefing, extra, overview, types, chart_images
    )
    return excel_bytes, pdf_bytes


def report_context(
    df: pd.DataFrame,
    source_name: str,
    generated_at: datetime,
    overview: dict[str, Any],
    types: dict[str, list[str]],
) -> dict[str, Any]:
    period = _period_label(df, types)
    prepared = (
        f"Prepared from {source_name} · {overview['rows']:,} rows"
        f" · generated {generated_at.strftime('%d %b %Y, %H:%M')}"
    )
    if period:
        prepared = f"{prepared} · {period}"
    return {
        "source_name": source_name,
        "generated_at": generated_at,
        "period": period,
        "prepared": prepared,
        "rows": overview["rows"],
        "columns": overview["columns"],
    }


def _period_label(df: pd.DataFrame, types: dict[str, list[str]]) -> str | None:
    if not types.get("datetime"):
        return None
    dates = coerce_datetime(df[types["datetime"][0]]).dropna()
    if dates.empty:
        return None
    start, end = dates.min(), dates.max()
    if pd.Timestamp(start).normalize() == pd.Timestamp(end).normalize():
        return pd.Timestamp(start).strftime("%d %b %Y")
    return f"{pd.Timestamp(start).strftime('%d %b %Y')} – {pd.Timestamp(end).strftime('%d %b %Y')}"


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
        ax.set_title(f"Histogram — {col}", color=INK, loc="left")
        ax.set_xlabel(col)
        ax.set_ylabel("Count")
        ax.set_facecolor(CREAM)
        fig.patch.set_facecolor(CREAM)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        images.append((f"hist_{col}", _fig_to_png(fig)))

    cat_cols = types["categorical"][:8]
    for col in cat_cols:
        counts = df[col].dropna().astype(str).value_counts().head(10)
        if counts.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.bar(counts.index.astype(str), counts.values, color=VIOLET)
        ax.set_title(f"Top values — {col}", color=INK, loc="left")
        ax.tick_params(axis="x", rotation=35)
        ax.set_facecolor(CREAM)
        fig.patch.set_facecolor(CREAM)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        images.append((f"bar_{col}", _fig_to_png(fig)))

    if len(types["numeric"]) >= 2:
        corr = df[types["numeric"]].apply(pd.to_numeric, errors="coerce").corr()
        from matplotlib.colors import LinearSegmentedColormap

        cmap = LinearSegmentedColormap.from_list("era", CORR_CMAP)
        fig, ax = plt.subplots(figsize=(6.5, 5.2))
        fig.patch.set_facecolor(CREAM)
        ax.set_facecolor(CREAM)
        im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.index)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.index)
        ax.set_title("Correlation heatmap", color=INK, loc="left")
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
            fig.patch.set_facecolor(CREAM)
            ax.set_facecolor(CREAM)
            ax.plot(paired["date"], paired["value"], color=TEAL, linewidth=2)
            ax.set_title(f"{num_col} over time", color=INK, loc="left")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.autofmt_xdate()
            images.append((f"ts_{num_col}", _fig_to_png(fig)))

    return images


def _fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=CREAM)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _build_excel(
    df: pd.DataFrame,
    context: dict[str, Any],
    briefing: list[Finding],
    extra: list[Finding],
    overview: dict[str, Any],
    types: dict[str, list[str]],
    chart_images: list[tuple[str, bytes]],
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 18, "font_color": INK, "font_name": "Calibri"}
        )
        subtitle_fmt = workbook.add_format(
            {"font_size": 11, "font_color": TEAL, "font_name": "Calibri"}
        )
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": INK,
                "font_color": CREAM,
                "border": 0,
                "font_name": "Calibri",
            }
        )
        label_fmt = workbook.add_format({"bold": True, "font_name": "Calibri", "font_color": INK})
        cell_fmt = workbook.add_format({"font_name": "Calibri", "font_color": MUTED})
        wrap_fmt = workbook.add_format({"font_name": "Calibri", "text_wrap": True, "valign": "top"})
        insight_fmt = workbook.add_format(
            {"font_name": "Calibri", "text_wrap": True, "bg_color": CREAM, "valign": "top"}
        )

        summary = workbook.add_worksheet("Summary")
        writer.sheets["Summary"] = summary
        summary.set_column("A:A", 28)
        summary.set_column("B:B", 88)
        summary.write("A1", "Analyst briefing", title_fmt)
        summary.write("A2", context["prepared"], subtitle_fmt)
        if context["period"]:
            summary.write("A3", f"Period: {context['period']}", subtitle_fmt)
        else:
            summary.write("A3", f"Source: {context['source_name']}", subtitle_fmt)

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
        summary.write(start, 0, "Briefing", header_fmt)
        summary.write(start, 1, "", header_fmt)
        summary.set_column("C:C", 72)
        if not briefing:
            summary.write(start + 1, 0, "No notable issues detected — this dataset looks clean.", insight_fmt)
            summary.write(start + 1, 1, "", insight_fmt)
            summary.set_row(start + 1, 28)
            row = start + 2
        else:
            row = start + 1
            for i, item in enumerate(briefing):
                summary.write(row, 0, f"{i + 1}. {item.lane.upper()}", label_fmt)
                summary.write(row, 1, f"{item.sentence}  {item.so_what}", insight_fmt)
                summary.set_row(row, 36)
                row += 1
        if extra:
            row += 1
            summary.write(row, 0, "Also noted", header_fmt)
            summary.write(row, 1, "", header_fmt)
            row += 1
            for item in extra:
                summary.write(row, 0, item.lane.upper(), label_fmt)
                summary.write(row, 1, f"{item.sentence}  {item.so_what}", insight_fmt)
                summary.set_row(row, 32)
                row += 1

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
    context: dict[str, Any],
    briefing: list[Finding],
    extra: list[Finding],
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
        title=f"Analyst briefing — {context['source_name']}",
    )
    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=26,
        textColor=colors.HexColor(INK),
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
        textColor=colors.HexColor(INK),
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
    story.append(Paragraph("Analyst briefing", cover_title))
    story.append(Paragraph(context["source_name"], cover_sub))
    if context["period"]:
        story.append(Paragraph(context["period"], cover_sub))
    story.append(Paragraph(context["prepared"], cover_sub))
    story.append(PageBreak())

    so_what = ParagraphStyle(
        "SoWhat",
        parent=body,
        textColor=colors.HexColor("#5C6568"),
        fontSize=10,
        leading=13,
        spaceAfter=10,
    )

    story.append(Paragraph("Key Insights", h1))
    if not briefing:
        story.append(
            Paragraph("No notable issues detected — this dataset looks clean.", body)
        )
    else:
        for i, item in enumerate(briefing, start=1):
            story.append(
                Paragraph(f"{i}. [{item.lane.upper()}] {item.sentence}", body)
            )
            story.append(Paragraph(item.so_what, so_what))
    if extra:
        story.append(Paragraph("Also noted", h1))
        for item in extra:
            story.append(Paragraph(f"[{item.lane.upper()}] {item.sentence}", body))
            story.append(Paragraph(item.so_what, so_what))

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
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(INK)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(CREAM)),
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor(CREAM)),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor(HAIR)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )
