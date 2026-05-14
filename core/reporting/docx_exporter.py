"""DOCX exporter for generated ICHIBAN seller-facing report text.

This exporter intentionally adds a structured Ruler Range visual from
report_input before converting the GPT markdown body. The report body remains
editable, but the top pricing lane now has a consistent Word-table visual.
"""

from __future__ import annotations

from io import BytesIO
import re
from typing import Any, Dict, Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
_MONEY_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _clean_inline_markdown(text: str) -> str:
    text = _BOLD_RE.sub(r"\1", text)
    return text.replace("__", "").strip()


def _money(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return str(value)
    return f"${number:,.0f}"


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _set_cell_text(cell, label: str, value: str = "", note: str = "") -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    r = p.add_run(label)
    r.bold = True
    r.font.size = Pt(7)

    if value:
        p.add_run("\n")
        r2 = p.add_run(value)
        r2.bold = True
        r2.font.size = Pt(8)

    if note:
        p.add_run("\n")
        r3 = p.add_run(note)
        r3.font.size = Pt(6)

    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _add_small_note(document: Document, text: str) -> None:
    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(90, 90, 90)


def _add_ruler_visual(document: Document, report_input: Dict[str, Any]) -> None:
    ruler = (report_input or {}).get("ruler_range") or {}
    pricing = (report_input or {}).get("pricing_reconciliation") or {}
    if not ruler and not pricing:
        return

    low = ruler.get("recommended_price_range_low") or pricing.get("recommended_price_range_low")
    high = ruler.get("recommended_price_range_high") or pricing.get("recommended_price_range_high")
    target = ruler.get("recommended_list_price") or pricing.get("recommended_list_price")
    evidence_low = ruler.get("ruler_low")
    evidence_high = ruler.get("ruler_high")

    document.add_heading("Recommended Range + Ruler", level=1)

    summary = document.add_paragraph()
    summary.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = summary.add_run(f"Recommended Market Entry Range: {_money(low)} - {_money(high)}")
    run.bold = True
    run.font.size = Pt(13)
    if target:
        summary.add_run("\n")
        target_run = summary.add_run(f"Target Position / Strategic List Posture: {_money(target)}")
        target_run.bold = True
        target_run.font.size = Pt(11)

    table = document.add_table(rows=2, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = True

    fills = ["D9EAD3", "E2F0D9", "FFF2CC", "FCE4D6", "F4CCCC"]
    headers = [
        ("Market Support", _money(evidence_low), "closed-comp floor"),
        ("Lower Entry", _money(low), "traffic posture"),
        ("Target Position", _money(target), "best lane"),
        ("Strategic Upper", _money(high), "strong presentation"),
        ("High-Risk Stretch", _money(evidence_high), "requires support"),
    ]

    for idx, (label, value, note) in enumerate(headers):
        cell = table.cell(0, idx)
        _set_cell_shading(cell, fills[idx])
        _set_cell_text(cell, label, value, note)

    arrow_text = "Market Support  →  Target Position  →  High-Risk Stretch"
    merged = table.cell(1, 0).merge(table.cell(1, 4))
    _set_cell_shading(merged, "F2F2F2")
    _set_cell_text(merged, arrow_text, "", "Pricing lane for discussion; not a guarantee")

    _add_small_note(
        document,
        "Ruler Range shows market evidence context. The Recommended Range is the narrower launch-pricing lane. The high-end marker is not an automatic list price.",
    )

    comments = ruler.get("range_indicator_comments") or []
    if comments:
        document.add_heading("Range Indicator Comments", level=2)
        comment_table = document.add_table(rows=1, cols=2)
        comment_table.style = "Table Grid"
        comment_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr = comment_table.rows[0].cells
        hdr[0].text = "Indicator"
        hdr[1].text = "Comment"
        for cell in hdr:
            _set_cell_shading(cell, "D9EAF7")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
        for item in comments:
            row = comment_table.add_row().cells
            row[0].text = str(item.get("label", ""))
            row[1].text = str(item.get("comment", ""))


def _add_markdown_line(document: Document, line: str) -> None:
    if line.startswith("### "):
        document.add_heading(_clean_inline_markdown(line[4:]), level=3)
    elif line.startswith("## "):
        document.add_heading(_clean_inline_markdown(line[3:]), level=2)
    elif line.startswith("# "):
        document.add_heading(_clean_inline_markdown(line[2:]), level=1)
    elif line.startswith(("- ", "• ")):
        document.add_paragraph(_clean_inline_markdown(line[2:]), style="List Bullet")
    elif re.match(r"^\d+\.\s+", line):
        document.add_paragraph(_clean_inline_markdown(re.sub(r"^\d+\.\s+", "", line)), style="List Number")
    else:
        document.add_paragraph(_clean_inline_markdown(line))


def _enforce_pricing_text(report_text: str, report_input: Optional[Dict[str, Any]]) -> str:
    """Keep exported DOCX pricing aligned with report_input even if old markdown exists."""
    if not report_text or not report_input:
        return report_text
    pricing = report_input.get("pricing_reconciliation") or {}
    low = _money(pricing.get("recommended_price_range_low"))
    high = _money(pricing.get("recommended_price_range_high"))
    if low == "—" or high == "—":
        return report_text
    desired = f"{low} — {high}"
    text = report_text
    text = re.sub(r"(?i)Market Opportunity", "High-Risk Stretch", text)
    text = re.sub(r"(?i)market opportunity", "High-Risk Stretch", text)
    text = re.sub(r"(?i)\breconciliation\b", "pricing basis", text)
    text = re.sub(
        r"(?i)(Recommended list price range[^:\n]*:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
        rf"\1{desired}",
        text,
    )
    text = re.sub(
        r"(?i)(Final suggested list range:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
        rf"\1{desired}",
        text,
    )
    text = re.sub(
        r"(?i)(Suggested list:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
        rf"\1{desired}",
        text,
    )
    text = re.sub(
        r"(?i)(Suggested list:\s*Price above\s*)\$[0-9,]+",
        rf"\1{high}",
        text,
    )
    text = re.sub(
        r"(?i)(Price above\s*)\$[0-9,]+",
        rf"\1{high}",
        text,
    )
    return text


def _is_generated_intro_line(normalized_line: str) -> bool:
    return (
        normalized_line.startswith("ichiban insight")
        or normalized_line.startswith("prepared for:")
        or normalized_line.startswith("subject:")
        or normalized_line.startswith("prepared:")
    )


def _starts_duplicate_ruler_block(normalized_line: str) -> bool:
    return (
        normalized_line.startswith("recommended range + ruler")
        or normalized_line.startswith("ruler range")
        or normalized_line.startswith("suggested list price range")
        or normalized_line.startswith("range indicator comments")
    )


def _ends_duplicate_ruler_block(normalized_line: str) -> bool:
    return (
        normalized_line.startswith("executive summary")
        or normalized_line.startswith("executive summary bullets")
        or normalized_line.startswith("comparable evidence")
        or normalized_line.startswith("subject property snapshot")
    )


def report_markdown_to_docx_bytes(
    report_text: str,
    title: Optional[str] = None,
    report_input: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Convert a markdown-like GPT report into an editable .docx file.

    When report_input is supplied, the exporter inserts a standardized Ruler
    Range visual and Range Indicator Comments before the narrative body.
    """
    document = Document()

    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)

    if title:
        document.add_heading(title, level=0)

    if report_input:
        _add_ruler_visual(document, report_input)

    report_text = _enforce_pricing_text(report_text or "", report_input)

    skip_duplicate_ruler_block = bool(report_input)
    skipping_duplicate_ruler = False

    for raw_line in (report_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            # Do not end duplicate-ruler skipping on blank lines. GPT output often
            # separates the duplicate heading, values, and notes with blank lines.
            continue

        normalized = line.lower().strip("# ").strip()

        # The exporter supplies its own title and top Ruler visual. Avoid duplicate
        # title/prepared metadata and duplicate pricing/ruler blocks from the GPT body.
        if skip_duplicate_ruler_block and _is_generated_intro_line(normalized):
            continue

        if skip_duplicate_ruler_block and _starts_duplicate_ruler_block(normalized):
            skipping_duplicate_ruler = True
            continue

        if skipping_duplicate_ruler:
            if _ends_duplicate_ruler_block(normalized):
                skipping_duplicate_ruler = False
            else:
                continue

        _add_markdown_line(document, line)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
