"""DOCX exporter for generated ICHIBAN seller-facing report text.

This exporter converts the GPT seller report into an editable DOCX.
The default package opens with the Recommended Range because the seller's
first question is where the property sits. The Seller Summary then explains
the "why," followed by the supporting market/detail report.
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
import re
from typing import Any, Dict, Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
_MONEY_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _configure_document_styles(document: Document) -> None:
    """Keep the Tarzan valuation export black-and-white and print-friendly."""
    for style_name, size, bold in [
        ("Normal", 10, False),
        ("Heading 1", 14, True),
        ("Heading 2", 12, True),
        ("Heading 3", 11, True),
        ("Title", 18, True),
    ]:
        try:
            style = document.styles[style_name]
            style.font.name = "Arial"
            style.font.size = Pt(size)
            style.font.bold = bold
            style.font.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass


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


def _money_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


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
    run.font.size = Pt(7)
    run.font.color.rgb = RGBColor(90, 90, 90)


def _set_table_borders(table, border_color: str = "000000", border_size: str = "8") -> None:
    """Apply simple black borders to every cell in a table."""
    for row in table.rows:
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_borders = tc_pr.find(qn("w:tcBorders"))
            if tc_borders is None:
                tc_borders = OxmlElement("w:tcBorders")
                tc_pr.append(tc_borders)
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                tag = qn(f"w:{edge}")
                element = tc_borders.find(tag)
                if element is None:
                    element = OxmlElement(f"w:{edge}")
                    tc_borders.append(element)
                element.set(qn("w:val"), "single")
                element.set(qn("w:sz"), border_size)
                element.set(qn("w:space"), "0")
                element.set(qn("w:color"), border_color)


def _set_cell_width(cell, width_twips: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_twips))
    tc_w.set(qn("w:type"), "dxa")


def _add_centered_cell_paragraph(cell, text: str, *, bold: bool = False, italic: bool = False, size: int = 10, underline: bool = False) -> None:
    p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.underline = underline
    r.font.size = Pt(size)


def _add_report_title(document: Document, title: Optional[str] = None, report_input: Optional[Dict[str, Any]] = None) -> None:
    """Add the locked report title block used by Tarzan valuation outputs."""
    report_input = report_input or {}
    package = report_input.get("report_package") or {}
    report_mode = package.get("report_mode") or (report_input.get("tarzan_report_standards") or report_input.get("bbc_tarzan_standards") or {}).get("report_mode") or "tarzan_valuation_analysis"
    report_date = report_input.get("report_date") or ""

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("ICHIBAN INSIGHT")
    r.bold = True
    r.font.size = Pt(18)

    if title:
        subtitle_text = str(title).replace("ICHIBAN INSIGHT - ", "").strip() or "Tarzan Valuation Analysis"
    else:
        subtitle_text = package.get("report_type") or package.get("resolved_report_label") or "Tarzan Valuation Analysis"

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(4)
    sr = subtitle.add_run(subtitle_text)
    sr.bold = True
    sr.font.size = Pt(12)

    if report_date:
        date_p = document.add_paragraph()
        date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_p.paragraph_format.space_after = Pt(8)
        dr = date_p.add_run(f"Report Date: {report_date}")
        dr.font.size = Pt(9)
        dr.italic = True


def _add_after_active_tactical_summary(document: Document, report_input: Dict[str, Any]) -> None:
    """Insert the standalone Current Market Context tactical headline when the report asks for it."""
    prefs = (report_input or {}).get("report_output_preferences") or {}
    if not prefs.get("report_starts_with_after_active_decision"):
        return
    decision = (report_input or {}).get("after_active_decision") or {}
    current = decision.get("current_listing_position") or {}
    market = decision.get("market_response") or {}
    tactical = decision.get("tactical_read") or {}
    background = decision.get("original_closed_comp_supported_range") or {}

    heading = document.add_paragraph()
    heading.paragraph_format.space_before = Pt(8)
    heading.paragraph_format.space_after = Pt(4)
    r = heading.add_run("Current Market Context")
    r.bold = True
    r.font.size = Pt(14)

    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.autofit = True
    rows = [
        ("Current List Price", _money(current.get("current_list_price"))),
        ("Original / Previous List Price", f"{_money(current.get('original_list_price'))} / {_money(current.get('previous_list_price'))}"),
        ("Current Days in MLS", str(current.get("days_in_mls") or "not supplied")),
        ("Showing / Offer Signal", f"Showings: {market.get('total_showings', 'not supplied')}; Last 7 days: {market.get('showings_last_7_days', 'not supplied')}; Offers: {market.get('offers_received', 'not supplied')}"),
        ("Current Action Range", f"{_money(tactical.get('current_action_range_low'))} — {_money(tactical.get('current_action_range_high'))}"),
        ("Next Number to Discuss", _money(tactical.get("next_number_to_discuss"))),
        ("Prior Comp-Supported Range", f"{background.get('display') or 'not supplied'} (background only)"),
        ("Current Tactical Read", str(tactical.get("price_action_now") or "not supplied")),
    ]
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value
        for cell in cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
        if cells[0].paragraphs and cells[0].paragraphs[0].runs:
            cells[0].paragraphs[0].runs[0].bold = True

    note = document.add_paragraph()
    note.paragraph_format.space_after = Pt(8)
    nr = note.add_run("Prior valuation support is background only in this standalone current market context review. Current buyer response and current user-entered updates control the tactical recommendation.")
    nr.italic = True
    nr.font.size = Pt(9)



def _is_tarzan_report_mode(report_input: Optional[Dict[str, Any]]) -> bool:
    """Return True when the active export is the Tarzan-only valuation branch."""
    if not isinstance(report_input, dict):
        return False
    package = report_input.get("report_package") or {}
    prefs = report_input.get("report_output_preferences") or {}
    standards = report_input.get("tarzan_report_standards") or report_input.get("bbc_tarzan_standards") or {}
    values = [
        report_input.get("report_mode"),
        report_input.get("report_type"),
        package.get("report_mode"),
        package.get("report_type"),
        prefs.get("package_structure"),
        standards.get("report_mode"),
        standards.get("active_output"),
    ]
    joined = " ".join(str(v or "") for v in values).lower()
    return "tarzan" in joined and "valuation" in joined

def _add_ruler_visual(document: Document, report_input: Dict[str, Any]) -> None:
    """Insert the standardized valuation range visual when requested.

    In Tarzan-only mode this is a valuation snapshot, not a seller circle sheet.
    BBC / seller presentation wording is reserved for the future BBC branch.
    """
    prefs = (report_input or {}).get("report_output_preferences") or {}
    if prefs.get("do_not_insert_standard_recommended_range_visual"):
        return
    if prefs.get("include_ruler_range") is False:
        return
    tarzan_mode = _is_tarzan_report_mode(report_input)

    ruler = (report_input or {}).get("ruler_range") or {}
    pricing = (report_input or {}).get("pricing_reconciliation") or {}
    if not ruler and not pricing:
        return

    low = ruler.get("recommended_price_range_low") or pricing.get("recommended_price_range_low")
    high = ruler.get("recommended_price_range_high") or pricing.get("recommended_price_range_high")
    target = ruler.get("recommended_list_price") or pricing.get("recommended_list_price")

    low_n = _money_number(low)
    high_n = _money_number(high)
    target_n = _money_number(target)
    invalid_range = (
        low_n is not None
        and high_n is not None
        and target_n is not None
        and not (low_n <= target_n <= high_n and low_n < high_n)
    )
    if invalid_range:
        warn = document.add_paragraph()
        warn.paragraph_format.space_after = Pt(8)
        run = warn.add_run(
            f"DATA CHECK REQUIRED: Recommended Range values are not in valid order. Low={_money(low)}, Recommended={_money(target)}, High={_money(high)}. Verify pricing_reconciliation before seller use."
        )
        run.bold = True
        run.font.size = Pt(10)
        return

    # Outer bordered box. In Tarzan mode this is evidence-oriented, not BBC styling.
    outer = document.add_table(rows=1, cols=1)
    outer.alignment = WD_TABLE_ALIGNMENT.CENTER
    outer.autofit = False
    _set_table_borders(outer, border_color="000000", border_size="12")
    outer_cell = outer.cell(0, 0)
    outer_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    outer_cell.text = ""

    heading = outer_cell.paragraphs[0]
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_after = Pt(6)
    heading.paragraph_format.space_before = Pt(8)
    run = heading.add_run("Tarzan Valuation Range Snapshot" if tarzan_mode else "Recommended Price Range")
    run.bold = True
    run.underline = True
    run.font.size = Pt(16)

    price_table = outer_cell.add_table(rows=2, cols=3)
    price_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    price_table.autofit = False
    price_table.style = "Table Grid"
    price_table.rows[0].height = Inches(0.32)
    price_table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    price_table.rows[1].height = Inches(0.55)
    price_table.rows[1].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    _set_table_borders(price_table, border_color="000000", border_size="6")

    headers = ["Bottom of Range", "Recommended Position", "Top of Range"]
    values = [_money(low), _money(target), _money(high)]
    for idx, header in enumerate(headers):
        header_cell = price_table.cell(0, idx)
        value_cell = price_table.cell(1, idx)
        _set_cell_width(header_cell, 2880)
        _set_cell_width(value_cell, 2880)
        header_cell.text = ""
        value_cell.text = ""
        hp = header_cell.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        hr = hp.add_run(header)
        hr.bold = True
        hr.font.size = Pt(10)
        vp = value_cell.paragraphs[0]
        vp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        vr = vp.add_run(values[idx])
        vr.bold = True
        vr.font.size = Pt(16)
        header_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        value_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        # Light grayscale is retained from the approved black-and-white sample.
        _set_cell_shading(header_cell, "EDEDED")

    outer_cell.add_paragraph()

    # Tick-mark ruler. Use a monospaced run for stable print alignment.
    ruler_amounts = outer_cell.add_paragraph()
    ruler_amounts.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ruler_amounts.paragraph_format.space_after = Pt(0)
    r = ruler_amounts.add_run(f"{_money(low):<28}{_money(target):^28}{_money(high):>28}")
    r.font.name = "Courier New"
    r._element.rPr.rFonts.set(qn('w:eastAsia'), "Courier New")
    r.font.size = Pt(9)

    ruler_line = outer_cell.add_paragraph()
    ruler_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ruler_line.paragraph_format.space_before = Pt(0)
    ruler_line.paragraph_format.space_after = Pt(6)
    lr = ruler_line.add_run("|-------------------------------|-------------------------------|")
    lr.font.name = "Courier New"
    lr._element.rPr.rFonts.set(qn('w:eastAsia'), "Courier New")
    lr.font.size = Pt(11)
    lr.bold = True

    if tarzan_mode:
        _add_centered_cell_paragraph(
            outer_cell,
            "Evidence snapshot only. Final status depends on comp fit, adjustment review, market momentum, concessions, and data verification.",
            italic=True,
            size=9,
        )
    else:
        _add_centered_cell_paragraph(
            outer_cell,
            "Seller-facing pricing note area reserved for the BBC branch.",
            italic=True,
            size=10,
        )

        notes = outer_cell.add_paragraph()
        notes.alignment = WD_ALIGN_PARAGRAPH.CENTER
        notes.paragraph_format.space_after = Pt(8)
        nr = notes.add_run("Seller Notes: ______________________________________________")
        nr.font.size = Pt(10)

def _add_agent_review_inputs(document: Document, report_input: Optional[Dict[str, Any]] = None) -> None:
    """Add the standard printed Realtor reminder section after the Recommended Range."""
    defaults = {
        "upgrades_condition": {
            "label": "Upgrades / Condition",
            "instruction": "Circle one",
            "options": [
                "Ultra Low",
                "Low",
                "Medium Low",
                "Medium",
                "Medium High",
                "High",
                "Fully Remodeled",
            ],
        },
        "buyer_confidence_risk_items": {
            "label": "Buyer Confidence / Risk Items",
            "instruction": "Circle / mark any that should be considered before pricing, launch, or negotiation strategy",
            "items": [
                "Roof",
                "Sewer scope",
                "Radon mitigation",
                "HVAC age / serviceability",
                "Smoke / odor concern",
                "Water intrusion / basement moisture",
                "Electrical / plumbing concerns",
                "Structural concerns",
                "Major deferred maintenance",
            ],
        },
    }

    supplied = (report_input or {}).get("agent_review_inputs") or {}
    upgrades = supplied.get("upgrades_condition") or defaults["upgrades_condition"]
    risks = supplied.get("buyer_confidence_risk_items") or defaults["buyer_confidence_risk_items"]

    document.add_heading("Agent Review Inputs", level=1)

    note = document.add_paragraph()
    note.paragraph_format.space_after = Pt(4)
    note_run = note.add_run(
        "Printed Realtor reminder section. Circle or mark items that may affect price position within the range, preparation before launch, buyer confidence, inspection leverage, or seller terms. These are not automatic price reductions."
    )
    note_run.italic = True
    note_run.font.size = Pt(8)
    note_run.font.color.rgb = RGBColor(90, 90, 90)

    table = document.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    headers = ["Upgrades / Condition", "Buyer Confidence / Risk Items"]
    for idx, header in enumerate(headers):
        cell = table.cell(0, idx)
        _set_cell_shading(cell, "EDEDED")
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(8)

    upgrade_options = upgrades.get("options") or defaults["upgrades_condition"]["options"]
    upgrade_cell = table.cell(1, 0)
    upgrade_cell.text = ""
    p = upgrade_cell.paragraphs[0]
    r = p.add_run("Circle one:\n")
    r.bold = True
    r.font.size = Pt(8)
    p.add_run(" | ".join(str(option) for option in upgrade_options))
    for paragraph in upgrade_cell.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(8)

    risk_items = risks.get("items") or defaults["buyer_confidence_risk_items"]["items"]
    risk_cell = table.cell(1, 1)
    risk_cell.text = ""
    p = risk_cell.paragraphs[0]
    r = p.add_run("Circle / mark any:\n")
    r.bold = True
    r.font.size = Pt(8)
    p.add_run("\n".join(f"○ {item}" for item in risk_items))
    for paragraph in risk_cell.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(8)



def _stack_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        return value
    try:
        number = float(value)
        if number == 0:
            return "$0"
        sign = "-" if number < 0 else ""
        return f"{sign}${abs(number):,.0f}"
    except Exception:
        return str(value)


def _add_logic_stack_table(document: Document, stack: Optional[Dict[str, Any]], *, title: str) -> None:
    """Insert a simple black-and-white stacked line-item table.

    This keeps the program output text/table based. It is intentionally not a
    graphic or chart; it gives GPT and the Realtor a readable map of the review layers.
    """
    stack = stack or {}
    rows = stack.get("rows") or []
    if not rows:
        return

    document.add_heading(title, level=1)

    if stack.get("not_a_second_valuation_model"):
        note = document.add_paragraph()
        note.paragraph_format.space_after = Pt(4)
        run = note.add_run(
            "Plain-language review stack only. This is not a second valuation model; comparable-specific adjustments remain in the comp grid."
        )
        run.italic = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(90, 90, 90)
    elif stack.get("separate_if_else_overlay"):
        note = document.add_paragraph()
        note.paragraph_format.space_after = Pt(4)
        run = note.add_run(
            "Current Market Context overlay only. This is separate from first-pass valuation logic and is used when market exposure or buyer response requires review."
        )
        run.italic = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(90, 90, 90)

    table = document.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    _set_table_borders(table, border_color="000000", border_size="6")

    headers = ["Step", "Review Item", "Adjustment / Result", "Notes"]
    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.text = header
        _set_cell_shading(cell, "EDEDED")
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(8)

    for item in rows:
        row = table.add_row().cells
        values = [
            str(item.get("step") or ""),
            str(item.get("review_item") or ""),
            _stack_value(item.get("adjustment_or_result")),
            str(item.get("notes") or ""),
        ]
        for idx, value in enumerate(values):
            row[idx].text = value
            for paragraph in row[idx].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(7)


def _add_pricing_logic_stack(document: Document, report_input: Optional[Dict[str, Any]] = None) -> None:
    stack = (report_input or {}).get("pricing_logic_stack") or {}
    _add_logic_stack_table(document, stack, title=stack.get("section_title") or "Recommended Price Logic")


def _add_after_active_logic_stack(document: Document, report_input: Optional[Dict[str, Any]] = None) -> None:
    stack = (report_input or {}).get("after_active_logic_stack") or {}
    if not stack:
        return
    _add_logic_stack_table(document, stack, title=stack.get("section_title") or "Current Market Context Logic Stack")

def _add_markdown_line(document: Document, line: str) -> None:
    if line.strip() in {"---", "***", "___"}:
        return
    if line.startswith("### "):
        document.add_heading(_clean_inline_markdown(line[4:]), level=3)
    elif line.startswith("## "):
        document.add_heading(_clean_inline_markdown(line[3:]), level=2)
    elif line.startswith("# "):
        document.add_heading(_clean_inline_markdown(line[2:]), level=1)
    elif _is_locked_report_section_heading(line):
        heading_text = re.sub(r"^\s*\d+\s*[\).:-]\s*", "", line).strip()
        document.add_heading(_clean_inline_markdown(heading_text), level=1)
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


LOCKED_REPORT_SECTION_STARTS = [
    "recommended range + ruler",
    "recommended range",
    "agent review inputs",
    "recommended price logic",
    "pricing logic stack",
    "after-active price logic stack",
    "after active price logic stack",
    "upgrades / condition",
    "buyer confidence / risk items",
    "the pricing decision",
    "why this range exists",
    "what supports the price",
    "what could weaken the price",
    "how the value was determined",
    "launch strategy",
    "bottom line",
    "additional notes provided",
    "data verification notes",
    "part 1 — bbc seller report",
    "part 1 - bbc seller report",
    "part 1 — seller summary",
    "part 1 - seller summary",
    "seller summary",
    "market acceptance / repositioning review",
    "market acceptance",
    "repositioning review",
    "seller strategy",
    "strategy / launch notes",
    "buyer considerations",
    "part 2 — tarzan analytical report",
    "part 2 - tarzan analytical report",
    "part 2 — supporting market detail",
    "part 2 - supporting market detail",
    "supporting market detail",
    "supporting data report",
    "executive summary",
    "comparable sales evidence",
    "comparable evidence",
    "how the value was determined",
    "generalized adjustments",
    "avm",
    "online benchmarks",
    "current competition check",
    "current competition",
    "market momentum",
    "price sensitivity & seller net behavior",
    "price sensitivity",
    "seller net behavior",
    "buyer considerations",
    "strategy",
    "launch notes",
    "disclaimer",
]


SELLER_CONFUSING_LINE_PHRASES = [
    "estimated 30-day success rate",
    "seller competition months",
    "months_of_seller_competition",
    "success rate high",
    "practical seller competition months",
]



def _normalize_report_line_for_matching(line: str) -> str:
    """Normalize GPT section labels so duplicate-skipping works with 1), 1., #, or plain headings."""
    normalized = (line or "").lower().strip().strip("# ").strip()
    normalized = re.sub(r"^\s*\d+\s*[\).:-]\s*", "", normalized).strip()
    normalized = re.sub(r"^\s*[ivx]+\s*[\).:-]\s*", "", normalized).strip()
    return normalized


def _is_locked_report_section_heading(line: str) -> bool:
    """Identify real report section headings without promoting ordinary sentences."""
    raw_line = (line or "").strip()
    normalized_line = _normalize_report_line_for_matching(raw_line)

    explicit_heading = raw_line.startswith("#") or bool(re.match(r"^\s*\d+\s*[\).:-]\s+", raw_line))
    heading_suffix_markers = (":", " —", " -", " /", " (", " &")

    for prefix in LOCKED_REPORT_SECTION_STARTS:
        if normalized_line == prefix:
            return True
        if explicit_heading and normalized_line.startswith(prefix):
            return True
        if any(normalized_line.startswith(prefix + marker) for marker in heading_suffix_markers):
            return True

    return False


def _starts_duplicate_ruler_block(normalized_line: str) -> bool:
    return (
        normalized_line.startswith("recommended range + ruler")
        or normalized_line.startswith("ruler range")
        or normalized_line.startswith("suggested list price range")
        or normalized_line.startswith("recommended price range")
        or normalized_line.startswith("recommended market entry range")
        or normalized_line.startswith("range indicator comments")
    )


def _ends_duplicate_ruler_block(normalized_line: str) -> bool:
    return (
        normalized_line.startswith("the pricing decision")
        or normalized_line.startswith("why this range exists")
        or normalized_line.startswith("what supports the price")
        or normalized_line.startswith("seller summary")
        or normalized_line.startswith("seller strategy")
        or normalized_line.startswith("strategy / launch notes")
        or normalized_line.startswith("buyer considerations")
        or normalized_line.startswith("part 2")
        or normalized_line.startswith("supporting market detail")
        or normalized_line.startswith("executive summary")
        or normalized_line.startswith("executive summary bullets")
        or normalized_line.startswith("comparable evidence")
        or normalized_line.startswith("subject property snapshot")
    )


def _sanitize_seller_facing_line(line: str) -> str:
    """Remove backend/engine wording from seller-facing DOCX output."""
    text = line or ""
    replacements = [
        (
            r"(?i)^\s*Limitations:\s*these counts come from the broader competition file and reflect the radius/filters used by the (?:engine|analysis); they inform launch posture and buyer alternatives but do not change the closed[-‑]comp support\.?\s*$",
            "How this affects the seller: these Active listings are not the closed sales used to set value; they are the current choices buyers will compare against this listing. More active choices usually means pricing and presentation need to be sharp from day one.",
        ),
        (
            r"(?i)^\s*Practical implication:\s*(\d+)\s+active alternatives means buyers have options; pricing near the top of the evidence band increases risk that buyer will choose a comparable active with superior presentation or a lower price\.?\s*$",
            r"Seller takeaway: with \1 Active alternatives, buyers have choices. A higher launch price can still work when presentation is strong, but if early showings or offers are weak, the seller should be ready to adjust quickly rather than wait until the listing reaches the active-market average Days in MLS.",
        ),
        (r"(?i)\bengine 1004MC inputs\b", "market-pattern inputs"),
        (r"(?i)\bengine's seller calculation\b", "seller-facing momentum review"),
        (r"(?i)\bengine’s seller calculation\b", "seller-facing momentum review"),
        (r"(?i)\bclassified as ([\"'][^\"']+[\"']) by the engine\b", r"supports a \1 market reading"),
        (r"(?i)\bclassified as ([^.;,]+) by the engine\b", r"supports a \1 market reading"),
        (r"(?i)\bthe engine applied\b", "the analysis considered"),
        (r"(?i)\bengine applied\b", "the analysis considered"),
        (r"(?i)\bthe engine found\b", "the analysis indicates"),
        (r"(?i)\bengine found\b", "the analysis indicates"),
        (r"(?i)\bthe engine used\b", "the analysis used"),
        (r"(?i)\bengine used\b", "the analysis used"),
        (r"(?i)\bthe engine preserved\b", "the analysis retained"),
        (r"(?i)\bnet_price\s*=\s*close_price\s*-\s*concessions\b", "net price reflects closed price less any reported concessions"),
        (r"(?i)\btime_adjustment\s*=\s*0\b", "no material time adjustment was applied"),
        (r"(?i)\bengine output\b", "adjusted analysis"),
        (r"(?i)\bthe engine's\b", "the analysis"),
        (r"(?i)\bthe engine’s\b", "the analysis"),
        (r"(?i)\bengine's\b", "analysis"),
        (r"(?i)\bengine’s\b", "analysis"),
        (r"(?i)\bHigh-Risk Stretch\b", "Top of Range"),
        (r"(?i)\bStrategic Upper\b", "Top of Range"),
        (r"(?i)\bby the engine\b", "by the analysis"),
        (r"(?i)\bengine\b", "analysis"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _should_skip_seller_confusing_line(line: str) -> bool:
    normalized = (line or "").lower()
    return any(phrase in normalized for phrase in SELLER_CONFUSING_LINE_PHRASES)


def _split_pipe_row(line: str) -> list[str]:
    cleaned = (line or "").strip()
    cleaned = re.sub(r"^[-•]\s*", "", cleaned).strip()
    if cleaned.startswith("Columns:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if cleaned.startswith("|") and cleaned.endswith("|"):
        cleaned = cleaned[1:-1]
    return [_clean_inline_markdown(part.strip()) for part in cleaned.split("|")]


def _looks_like_pipe_table_row(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped or "|" not in stripped:
        return False
    if re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", stripped):
        return False
    return len(_split_pipe_row(stripped)) >= 3


def _clean_table_header(header: str) -> str:
    text = _clean_inline_markdown(header or "")
    text = re.sub(r"(?i)\s*\(engine\)\s*", "", text)
    text = re.sub(r"(?i)\s*\(selected comps\)\s*", "", text)
    if text.lower().startswith("total adjusted price"):
        return "Total Adjusted Price"
    return text.strip()


def _clean_table_value_for_header(value: str, header: str) -> str:
    """Remove repeated labels from GPT pipe rows once a real table header exists."""
    text = _clean_inline_markdown(value or "")
    normalized_header = _clean_table_header(header or "").lower()
    patterns: list[str] = []
    if "closed" in normalized_header or "net" in normalized_header:
        patterns.extend([r"(?i)^closed\s*/\s*net\s*price\s*:\s*", r"(?i)^closed\s*net\s*:\s*", r"(?i)^closed\s*:\s*"])
    if "close date" in normalized_header:
        patterns.append(r"(?i)^close\s*date\s*:\s*")
    if "days" in normalized_header:
        patterns.append(r"(?i)^days\s*in\s*mls\s*:\s*")
    if "adjusted" in normalized_header:
        patterns.append(r"(?i)^total\s*adjusted\s*price\s*:\s*")
    for pattern in patterns:
        text = re.sub(pattern, "", text).strip()

    if "closed" in normalized_header or "net" in normalized_header:
        text = re.sub(r"\s*[→➔]\s*Net\s*:\s*", "\nNet: ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+Net\s*:\s*", "\nNet: ", text, flags=re.IGNORECASE)

    if "close date" in normalized_header:
        match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
        if match:
            try:
                parsed = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                return parsed.strftime("%m/%d/%Y")
            except Exception:
                return text

    return text


def _add_simple_docx_table(document: Document, headers: list[str], rows: list[list[str]]) -> None:
    if not headers or not rows:
        return

    headers = [_clean_table_header(header) for header in headers]
    column_count = len(headers)
    table = document.add_table(rows=1, cols=column_count)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    header_cells = table.rows[0].cells
    for idx, header in enumerate(headers):
        header_cells[idx].text = header
        _set_cell_shading(header_cells[idx], "EDEDED")
        for paragraph in header_cells[idx].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(8)

    for row_values in rows:
        row = table.add_row().cells
        padded = list(row_values[:column_count]) + [""] * max(0, column_count - len(row_values))
        for idx, value in enumerate(padded[:column_count]):
            row[idx].text = _clean_table_value_for_header(value, headers[idx])
            for paragraph in row[idx].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(7)


def _try_add_following_pipe_table(document: Document, lines: list[str], start_index: int) -> int:
    """Parse either a Columns: header or a direct markdown pipe table into a real Word table."""
    i = start_index
    while i < len(lines) and not lines[i].strip():
        i += 1

    if i >= len(lines):
        return start_index

    header_line = lines[i].strip()
    direct_markdown_header = _looks_like_pipe_table_row(header_line)
    columns_header = header_line.lower().startswith("columns:") and "|" in header_line

    if not (columns_header or direct_markdown_header):
        return start_index

    headers = _split_pipe_row(header_line)
    rows: list[list[str]] = []
    i += 1

    # Optional markdown separator row: |---|---:| etc.
    if i < len(lines) and re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", lines[i].strip()):
        i += 1

    while i < len(lines):
        candidate = lines[i].strip()
        if not candidate:
            i += 1
            continue
        normalized = _normalize_report_line_for_matching(candidate)
        if _is_locked_report_section_heading(candidate) and not _looks_like_pipe_table_row(candidate):
            break
        if not _looks_like_pipe_table_row(candidate):
            break
        rows.append(_split_pipe_row(candidate))
        i += 1

    if rows:
        _add_simple_docx_table(document, headers, rows)
        return i

    return start_index

def report_markdown_to_docx_bytes(
    report_text: str,
    title: Optional[str] = None,
    report_input: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Convert a markdown-like GPT report into an editable .docx file.

    When report_input is supplied, the exporter inserts the standardized Ruler
    Range visual when it reaches the seller-facing Recommended Range section.
    """
    document = Document()
    _configure_document_styles(document)

    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)

    if title or report_input:
        _add_report_title(document, title=title, report_input=report_input)

    # The locked range visual and Agent Review Inputs are template-owned, not GPT-owned.
    # Insert them once at the top of every seller report, then skip any duplicate
    # markdown/table versions GPT may produce.
    if report_input:
        prefs = (report_input.get("report_output_preferences") or {}) if isinstance(report_input, dict) else {}
        tarzan_mode = _is_tarzan_report_mode(report_input)
        _add_after_active_tactical_summary(document, report_input)
        _add_ruler_visual(document, report_input)
        if prefs.get("include_agent_review_inputs") is True and not prefs.get("do_not_insert_standard_recommended_range_visual") and not tarzan_mode:
            _add_agent_review_inputs(document, report_input)
        if prefs.get("include_pricing_logic_stack", True) is not False:
            _add_pricing_logic_stack(document, report_input)

    report_text = _enforce_pricing_text(report_text or "", report_input)

    skip_duplicate_ruler_block = bool(report_input)
    skipping_duplicate_ruler = False
    skipping_duplicate_agent_review = False
    after_active_stack_inserted = False

    lines = (report_text or "").splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = _sanitize_seller_facing_line(raw_line.strip())
        if not line:
            # Do not end duplicate-ruler skipping on blank lines. GPT output often
            # separates the duplicate heading, values, and notes with blank lines.
            index += 1
            continue

        if _should_skip_seller_confusing_line(line):
            index += 1
            continue

        normalized = _normalize_report_line_for_matching(line)

        # The exporter supplies its own title and top Ruler visual. Avoid duplicate
        # title/prepared metadata and duplicate pricing/ruler blocks from the GPT body.
        if skip_duplicate_ruler_block and _is_generated_intro_line(normalized):
            index += 1
            continue

        if report_input and (
            normalized.startswith("recommended range")
            or normalized.startswith("recommended price range")
            or normalized == "ruler range"
        ):
            skipping_duplicate_ruler = True
            index += 1
            continue

        if report_input and normalized.startswith("agent review inputs"):
            skipping_duplicate_agent_review = True
            index += 1
            continue

        if report_input and normalized.startswith(("recommended price logic", "pricing logic stack", "after-active price logic stack", "after active price logic stack")):
            # Template-owned tables are inserted above from structured report_input.
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate:
                    index += 1
                    continue
                if _is_locked_report_section_heading(candidate) and not _looks_like_pipe_table_row(candidate):
                    break
                index += 1
            continue

        if skip_duplicate_ruler_block and _starts_duplicate_ruler_block(normalized):
            skipping_duplicate_ruler = True
            index += 1
            continue

        if skipping_duplicate_ruler:
            if _ends_duplicate_ruler_block(normalized):
                skipping_duplicate_ruler = False
            else:
                index += 1
                continue

        if skipping_duplicate_agent_review:
            numbered_or_named_section = bool(re.match(r"^\s*\d+\s*[\).:-]\s+", raw_line.strip())) or _is_locked_report_section_heading(line)
            if numbered_or_named_section and not normalized.startswith(("upgrades / condition", "buyer confidence / risk items")):
                skipping_duplicate_agent_review = False
            else:
                index += 1
                continue

        if normalized.startswith("part 1") or normalized.startswith("bbc seller report"):
            if report_input and _is_tarzan_report_mode(report_input):
                index += 1
                continue
            document.add_heading("PART 1 — BBC SELLER REPORT", level=1)
            index += 1
            continue

        if normalized.startswith("part 2") or normalized.startswith("tarzan analytical report") or normalized.startswith("supporting market detail") or normalized.startswith("supporting data report"):
            if report_input and _is_tarzan_report_mode(report_input):
                document.add_heading("Tarzan Valuation Analysis", level=1)
            else:
                document.add_page_break()
                document.add_heading("PART 2 — TARZAN ANALYTICAL REPORT", level=1)
            index += 1
            continue

        if normalized.startswith("after-active property review") or normalized.startswith("after active property review"):
            document.add_heading("Current Market Context Review", level=1)
            if report_input and not after_active_stack_inserted:
                _add_after_active_logic_stack(document, report_input)
                after_active_stack_inserted = True
            index += 1
            continue

        if normalized.startswith("comparable sales evidence") or normalized.startswith("comparable evidence"):
            document.add_heading("Comparable Evidence", level=1)
            next_index = _try_add_following_pipe_table(document, lines, index + 1)
            if next_index != index + 1:
                index = next_index
                continue
            index += 1
            continue

        if (line.lower().startswith("columns:") and "|" in line) or _looks_like_pipe_table_row(line):
            next_index = _try_add_following_pipe_table(document, lines, index)
            if next_index != index:
                index = next_index
                continue

        _add_markdown_line(document, line)
        index += 1

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
