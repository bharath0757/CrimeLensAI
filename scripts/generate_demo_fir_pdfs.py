"""Generate polished, text-based FIR PDFs for the judge demonstration."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "demo" / "firs"
OUTPUT_DIR = ROOT / "output" / "pdf" / "demo-firs"


def safe_text(value: str) -> str:
    """Use ReportLab-safe text while preserving extractor-visible identifiers."""
    return (
        value.replace("\N{EM DASH}", "-")
        .replace("\N{EN DASH}", "-")
        .replace("\N{INDIAN RUPEE SIGN}", "INR ")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def parse_source(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    metadata: dict[str, str] = {}
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines[2:]:
        stripped = line.strip()
        match = re.match(r"^(FIR number|Date|Police station):\s*(.+)$", stripped)
        if match:
            metadata[match.group(1)] = match.group(2)
            continue
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("All names, identifiers and events in this file"):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return metadata, paragraphs


def page_decor(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0B3558"))
    canvas.rect(0, height - 24 * mm, width, 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#39A5C8"))
    canvas.circle(21 * mm, height - 12 * mm, 3 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#80C5DA"))
    canvas.circle(29 * mm, height - 12 * mm, 3 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#D9EDF4"))
    canvas.circle(37 * mm, height - 12 * mm, 3 * mm, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor("#D8E2EA"))
    canvas.line(18 * mm, 17 * mm, width - 18 * mm, 17 * mm)
    canvas.setFillColor(colors.HexColor("#526575"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 11 * mm, "Synthetic demonstration record - not a real police complaint")
    canvas.drawRightString(width - 18 * mm, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(source: Path, destination: Path) -> None:
    metadata, paragraphs = parse_source(source)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "FirTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#142A3B"),
        alignment=TA_LEFT,
        spaceAfter=5 * mm,
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0B5F82"),
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=15,
        textColor=colors.HexColor("#243746"),
        alignment=TA_LEFT,
        spaceAfter=3.2 * mm,
    )
    notice = ParagraphStyle(
        "Notice",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#8A3A00"),
        backColor=colors.HexColor("#FFF2D8"),
        borderColor=colors.HexColor("#E6A23C"),
        borderWidth=0.8,
        borderPadding=8,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    doc = BaseDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=34 * mm,
        bottomMargin=24 * mm,
        title=f"{metadata['FIR number']} - Synthetic FIR",
        author="CrimeLensAI",
        subject="Synthetic FIR for criminal-network analysis demonstration",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="body",
    )
    doc.addPageTemplates(PageTemplate(id="fir", frames=[frame], onPage=page_decor))

    story = [
        Paragraph("FIRST INFORMATION REPORT", title),
        Paragraph(
            "This is a fabricated report for software testing. It is not a real allegation.",
            notice,
        ),
    ]
    rows = [
        ["FIR Number", safe_text(metadata["FIR number"])],
        ["Date", safe_text(metadata["Date"])],
        ["Police Station", safe_text(metadata["Police station"])],
    ]
    table = Table(rows, colWidths=[38 * mm, 126 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1F5")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#29485F")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D7E0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 5 * mm), Paragraph("COMPLAINT NARRATIVE", section)])
    for paragraph in paragraphs:
        story.append(Paragraph(safe_text(paragraph), body))
    story.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("INVESTIGATOR NOTE", section),
            Paragraph(
                "Entity matches and graph connections generated from this report are investigative leads, not findings of guilt. Officers must verify every source and follow applicable legal procedure.",
                body,
            ),
        ]
    )
    doc.build(story)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCE_DIR.glob("[0-9][0-9]-*.txt"))
    if len(sources) != 5:
        raise RuntimeError(f"Expected five demo FIR sources, found {len(sources)}")
    for source in sources:
        destination = OUTPUT_DIR / f"{source.stem}.pdf"
        build_pdf(source, destination)
        print(destination)


if __name__ == "__main__":
    main()
