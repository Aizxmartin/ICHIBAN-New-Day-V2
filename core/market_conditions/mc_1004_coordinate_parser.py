from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re


PERIOD_MONTHS = {
    "prior_7_12": 6,
    "prior_4_6": 3,
    "current_3": 3,
}


def parse_1004mc_coordinate_table(file_path: str | Path) -> Dict[str, Any]:
    """
    Parse a text-layer REcolorado / Crystal Reports 1004MC PDF.

    Why this parser exists:
    REcolorado's direct-download 1004MC has a real text layer, but the text
    stream is not stored in normal visual reading order. The raw text often
    looks scrambled even though the report looks clean on screen.

    Example text stream pattern from Year 1:
        87.33 3.54 309 262 Total # of Comparable Sales...
        ... Months of Housing Supply ...
        2.78 176 190 63.33 89.83 1.94 174 539

    Visual table meaning:
        Prior 7-12: sales 539, absorption 89.83, active 174, supply 1.94
        Prior 4-6:  sales 190, absorption 63.33, active 176, supply 2.78
        Current-3:  sales 262, absorption 87.33, active 309, supply 3.54

    This parser handles that known Crystal Reports export pattern first.
    """

    path = Path(file_path)

    result: Dict[str, Any] = {
        "parsed": False,
        "values": {},
        "warnings": [],
        "validation": {},
        "pages_checked": 0,
        "method": "recolorado_crystal_textstream_1004mc",
        "debug": {},
    }

    if not path.exists():
        result["warnings"].append("File does not exist.")
        return result

    text = _extract_pdf_text(path)
    clean = _clean_text(text)

    result["debug"]["total_text_characters"] = len(clean)
    result["debug"]["raw_text_sample"] = clean[:1500]

    if not clean:
        result["warnings"].append("No usable text was found.")
        return result

    year1 = _extract_section(
        clean,
        start_label="Year 1 - Current to 12 Months",
        end_labels=[
            "Generated on:",
            "1004MC Addendum Detail Page 1",
            "Year 2 -",
            "Year 2",
        ],
    )

    if not year1:
        result["warnings"].append("Could not find Year 1 - Current to 12 Months section.")
        return result

    values: Dict[str, Any] = {}

    inventory_values = _parse_year1_inventory_analysis(year1)
    median_values = _parse_year1_median_price_dim(year1)

    values.update(inventory_values)
    values.update(median_values)

    result["values"] = values
    result["validation"] = _validate_values(values)

    if _has_enough_values(values):
        result["parsed"] = True

        if not result["validation"].get("inventory_math_ok"):
            result["warnings"].append(
                "1004MC values were parsed, but inventory math did not fully validate. Review before using."
            )
    else:
        result["warnings"].append(
            "Could not parse enough Year 1 1004MC values. Use manual entry."
        )

    return result


# ---------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------

def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ImportError("pypdf is required. Install with: py -m pip install pypdf") from exc

    reader = PdfReader(str(path))
    parts: List[str] = []

    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
            parts.append(page_text)
        except Exception:
            continue

    return "\n".join(parts)


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = _fix_glued_decimal_numbers(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()


def _fix_glued_decimal_numbers(text: str) -> str:
    """
    Crystal Reports sometimes glues values together:
        63.3389.83
    This should be read as:
        63.33 89.83
    """

    previous = None
    current = text

    while previous != current:
        previous = current
        current = re.sub(
            r"(\d+\.\d{2})(\d+\.\d{2})",
            r"\1 \2",
            current,
        )

    return current


# ---------------------------------------------------------------------
# Year 1 parsing
# ---------------------------------------------------------------------

def _parse_year1_inventory_analysis(year1_text: str) -> Dict[str, Any]:
    """
    Parse the Inventory Analysis section.

    Expected visual values from the user's screenshot:

    Prior 7-12:
        sales 539
        absorption 89.83
        active listings 174
        months supply 1.94

    Prior 4-6:
        sales 190
        absorption 63.33
        active listings 176
        months supply 2.78

    Current-3:
        sales 262
        absorption 87.33
        active listings 309
        months supply 3.54
    """

    values: Dict[str, Any] = {}

    inventory = _extract_section(
        year1_text,
        start_label="Inventory Analysis",
        end_labels=["Median Price & DIM"],
    )

    if not inventory:
        return values

    split = re.split(
        r"Total\s*#\s*of\s*Comparable\s*Sales\s*\(Settled\)",
        inventory,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(split) < 2:
        return values

    before_label = split[0]
    after_label = split[1]

    # The current-3 values appear immediately before the row labels.
    # Raw order observed:
    #   87.33 3.54 309 262
    # Meaning:
    #   absorption, months_supply, active_listings, sales
    before_tokens = _numeric_tokens(before_label)
    current_block = before_tokens[-4:] if len(before_tokens) >= 4 else []

    if len(current_block) == 4:
        values["current_3_absorption_rate"] = _to_float(current_block[0])
        values["current_3_months_supply"] = _to_float(current_block[1])
        values["current_3_active_listings"] = _to_int(current_block[2])
        values["current_3_sales"] = _to_int(current_block[3])

    after_until_median = _extract_before_any(
        after_label,
        ["Median Price & DIM"],
    )

    after_tokens = _numeric_tokens(after_until_median)

    # Raw order observed after the labels:
    #   2.78 176 190 63.33 89.83 1.94 174 539
    #
    # Meaning:
    #   Prior 4-6:  months_supply, active_listings, sales, absorption
    #   Prior 7-12: absorption, months_supply, active_listings, sales
    if len(after_tokens) >= 8:
        values["prior_4_6_months_supply"] = _to_float(after_tokens[0])
        values["prior_4_6_active_listings"] = _to_int(after_tokens[1])
        values["prior_4_6_sales"] = _to_int(after_tokens[2])
        values["prior_4_6_absorption_rate"] = _to_float(after_tokens[3])

        values["prior_7_12_absorption_rate"] = _to_float(after_tokens[4])
        values["prior_7_12_months_supply"] = _to_float(after_tokens[5])
        values["prior_7_12_active_listings"] = _to_int(after_tokens[6])
        values["prior_7_12_sales"] = _to_int(after_tokens[7])

    return values


def _parse_year1_median_price_dim(year1_text: str) -> Dict[str, Any]:
    """
    Parse the Median Price & DIM section.

    Expected visual values from the user's screenshot:

    Prior 7-12:
        close price 575000
        sales DIM 25
        list price 523995
        listings DIM 135
        sale/list pct 0.00

    Prior 4-6:
        close price 575500
        sales DIM 45
        list price 479000
        listings DIM 116
        sale/list pct 96.08

    Current-3:
        close price 604900
        sales DIM 17
        list price 529900
        listings DIM 40
        sale/list pct 98.77
    """

    values: Dict[str, Any] = {}

    median_section = _extract_section(
        year1_text,
        start_label="Median Price & DIM",
        end_labels=[
            "*For the 7-12 Months",
            "* For the 7-12 Months",
            "Generated on:",
            "1004MC Addendum Detail Page 1",
        ],
    )

    if not median_section:
        return values

    # Strip header text up to the last period header.
    # The direct-download text stream usually has:
    #   Current - 3 Months Prior 4-6 Months Prior 7-12 Months 17 $604,900 ...
    header_match = re.search(
        r"Prior\s*7-12\s*Months\s+(?P<body>.*)",
        median_section,
        flags=re.IGNORECASE,
    )

    body = header_match.group("body") if header_match else median_section

    tokens = _numeric_tokens(body)

    # Expected token order:
    #   17, $604900, 45, $575500, 25, $575000,
    #   40, $529900, 116, $479000, 135, $523995,
    #   98.77%, 96.08%, 0.00%
    #
    # Meaning:
    #   Current sales_dim, current close,
    #   Prior4 sales_dim, prior4 close,
    #   Prior7 sales_dim, prior7 close,
    #   Current listings_dim, current list,
    #   Prior4 listings_dim, prior4 list,
    #   Prior7 listings_dim, prior7 list,
    #   Current pct, prior4 pct, prior7 pct

    if len(tokens) >= 6:
        values["current_3_median_sales_dim"] = _to_int(tokens[0])
        values["current_3_median_close_price"] = _to_int(tokens[1])

        values["prior_4_6_median_sales_dim"] = _to_int(tokens[2])
        values["prior_4_6_median_close_price"] = _to_int(tokens[3])

        values["prior_7_12_median_sales_dim"] = _to_int(tokens[4])
        values["prior_7_12_median_close_price"] = _to_int(tokens[5])

    if len(tokens) >= 12:
        values["current_3_median_listings_dim"] = _to_int(tokens[6])
        values["current_3_median_list_price"] = _to_int(tokens[7])

        values["prior_4_6_median_listings_dim"] = _to_int(tokens[8])
        values["prior_4_6_median_list_price"] = _to_int(tokens[9])

        values["prior_7_12_median_listings_dim"] = _to_int(tokens[10])
        values["prior_7_12_median_list_price"] = _to_int(tokens[11])

    if len(tokens) >= 15:
        values["current_3_median_sale_to_list_price_pct"] = _to_float(tokens[12])
        values["prior_4_6_median_sale_to_list_price_pct"] = _to_float(tokens[13])
        values["prior_7_12_median_sale_to_list_price_pct"] = _to_float(tokens[14])

    return values


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def _validate_values(values: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Any] = {
        "inventory_math_ok": True,
        "absorption_checks": {},
        "months_supply_checks": {},
    }

    for period_key, months in PERIOD_MONTHS.items():
        sales = values.get(f"{period_key}_sales")
        absorption = values.get(f"{period_key}_absorption_rate")
        active = values.get(f"{period_key}_active_listings")
        supply = values.get(f"{period_key}_months_supply")

        if sales is not None and absorption not in (None, 0):
            expected_abs = round(float(sales) / months, 2)
            actual_abs = round(float(absorption), 2)
            ok = abs(expected_abs - actual_abs) <= 0.20

            checks["absorption_checks"][period_key] = {
                "expected": expected_abs,
                "actual": actual_abs,
                "ok": ok,
            }

            if not ok:
                checks["inventory_math_ok"] = False

        if active is not None and absorption not in (None, 0) and supply is not None:
            expected_supply = round(float(active) / float(absorption), 2)
            actual_supply = round(float(supply), 2)
            ok = abs(expected_supply - actual_supply) <= 0.20

            checks["months_supply_checks"][period_key] = {
                "expected": expected_supply,
                "actual": actual_supply,
                "ok": ok,
            }

            if not ok:
                checks["inventory_math_ok"] = False

    return checks


def _has_enough_values(values: Dict[str, Any]) -> bool:
    required = [
        "prior_7_12_sales",
        "prior_4_6_sales",
        "current_3_sales",
        "prior_7_12_absorption_rate",
        "prior_4_6_absorption_rate",
        "current_3_absorption_rate",
        "prior_7_12_active_listings",
        "prior_4_6_active_listings",
        "current_3_active_listings",
        "prior_7_12_months_supply",
        "prior_4_6_months_supply",
        "current_3_months_supply",
        "prior_7_12_median_close_price",
        "prior_4_6_median_close_price",
        "current_3_median_close_price",
    ]

    found = sum(values.get(key) is not None for key in required)
    return found >= 12


# ---------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------

def _extract_section(text: str, start_label: str, end_labels: List[str]) -> str:
    start = re.search(re.escape(start_label), text, flags=re.IGNORECASE)

    if not start:
        return ""

    tail = text[start.end():]
    end_positions = []

    for label in end_labels:
        found = re.search(re.escape(label), tail, flags=re.IGNORECASE)

        if found:
            end_positions.append(found.start())

    if end_positions:
        return tail[:min(end_positions)].strip()

    return tail.strip()


def _extract_before_any(text: str, labels: List[str]) -> str:
    end_positions = []

    for label in labels:
        found = re.search(re.escape(label), text, flags=re.IGNORECASE)

        if found:
            end_positions.append(found.start())

    if end_positions:
        return text[:min(end_positions)].strip()

    return text.strip()


def _numeric_tokens(text: str) -> List[str]:
    """
    Extract numeric tokens while preserving money and percent values.

    Handles:
        $604,900
        98.77%
        87.33
        309
    """

    text = _fix_glued_decimal_numbers(text)

    pattern = r"\$?\d[\d,]*(?:\.\d+)?%?"
    return re.findall(pattern, text)


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    cleaned = re.sub(r"[^0-9\-]", "", str(value))

    if cleaned in ("", "-"):
        return None

    try:
        return int(cleaned)
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    cleaned = str(value)
    cleaned = cleaned.replace("$", "")
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("%", "")
    cleaned = cleaned.strip()

    if cleaned in ("", "-"):
        return None

    try:
        return float(cleaned)
    except Exception:
        return None