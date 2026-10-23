from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import shutil
import subprocess
import tempfile

from .mc_1004_coordinate_parser import parse_1004mc_coordinate_table


@dataclass
class MarketConditions1004MC:
    """
    1004MC parser result.

    The router handles:
    1. Image-only/rotated PDFs -> manual/OCR fallback
    2. Text-layer Crystal Reports PDFs -> coordinate/table parser
    3. Text-layer but failed table validation -> manual review
    """

    source: str = "1004mc"
    file_path: Optional[str] = None

    text_found: bool = False
    image_only: bool = False
    rotated_or_image_form: bool = False

    page_count: Optional[int] = None
    total_text_characters: int = 0

    recommended_route: str = "manual_1004mc_entry"
    parser_confidence: str = "low"
    parser_method: str = ""

    current_3_sales: Optional[int] = None
    prior_4_6_sales: Optional[int] = None
    prior_7_12_sales: Optional[int] = None

    current_3_absorption_rate: Optional[float] = None
    prior_4_6_absorption_rate: Optional[float] = None
    prior_7_12_absorption_rate: Optional[float] = None

    current_3_active_listings: Optional[int] = None
    prior_4_6_active_listings: Optional[int] = None
    prior_7_12_active_listings: Optional[int] = None

    current_3_months_supply: Optional[float] = None
    prior_4_6_months_supply: Optional[float] = None
    prior_7_12_months_supply: Optional[float] = None

    current_3_median_close_price: Optional[int] = None
    prior_4_6_median_close_price: Optional[int] = None
    prior_7_12_median_close_price: Optional[int] = None

    current_3_median_sales_dim: Optional[int] = None
    prior_4_6_median_sales_dim: Optional[int] = None
    prior_7_12_median_sales_dim: Optional[int] = None

    current_3_median_list_price: Optional[int] = None
    prior_4_6_median_list_price: Optional[int] = None
    prior_7_12_median_list_price: Optional[int] = None

    current_3_median_listings_dim: Optional[int] = None
    prior_4_6_median_listings_dim: Optional[int] = None
    prior_7_12_median_listings_dim: Optional[int] = None

    current_3_median_sale_to_list_price_pct: Optional[float] = None
    prior_4_6_median_sale_to_list_price_pct: Optional[float] = None
    prior_7_12_median_sale_to_list_price_pct: Optional[float] = None

    validation: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    raw_text_sample: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



def _ocr_pdf_first_page(path: Path) -> tuple[str, str]:
    """Render page 1 and OCR it when the PDF contains a rasterized report.

    Returns (text, method). This is an optional fallback: if Tesseract is not
    installed, the caller receives an empty string and can offer manual entry.
    """
    if shutil.which("tesseract") is None:
        return "", "ocr_unavailable_tesseract_missing"
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        if len(doc) < 1:
            return "", "ocr_no_pages"
        page = doc[0]
        # 3.0x is deliberate. At 2.2x, thin digits in the Matrix browser-print
        # PDF (for example "91") can lose the leading digit during OCR.
        pix = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), alpha=False)
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "1004mc_page1.png"
            pix.save(str(image_path))
            proc = subprocess.run(
                ["tesseract", str(image_path), "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if proc.returncode != 0:
                return "", "ocr_tesseract_failed"
            return proc.stdout or "", "tesseract_visual_table"
    except Exception:
        return "", "ocr_exception"


def _parse_visual_ocr_table(text: str) -> Dict[str, Any]:
    """Parse OCR text where each 1004MC row appears in visual left-to-right order."""
    clean = re.sub(r"[ \t]+", " ", text.replace("\u2019", "'").replace("\u2018", "'"))
    values: Dict[str, Any] = {}

    def row(pattern: str, count: int = 3):
        m = re.search(pattern + r"\s+([^\n]+)", clean, flags=re.IGNORECASE)
        if not m:
            return []
        tokens = re.findall(r"\$?[\d,]+(?:\.\d+)?%?", m.group(1))
        return tokens[:count]

    rows = {
        "sales": row(r"Total\s*#\s*of\s*Comparable\s*Sales\s*\(Settled\)"),
        "absorption": row(r"Absorption\s*Rate\s*\(Total\s*Sales/Months\)"),
        "active": row(r"Total\s*#\s*of\s*Comparable\s*Active\s*Listings"),
        # Matrix browser-print OCR may drop the closing parenthesis after
        # "Lst/Ab. Rate". Stop at either the closing parenthesis or the word
        # Rate so the three numeric values remain available to the row parser.
        "supply": row(
            r"Months\s*of\s*Housing\s*Supply(?:\s*\([^\n]*?(?:\)|Rate))?"
        ),
        "close": row(r"Median\s*Comparable\s*Close\s*Price"),
        "sales_dim": row(r"Median\s*Comparable\s*Sales\s*DIM"),
        "list": row(r"Median\s*Comparable\s*List\s*Price\s*\(Listings\s*Only\)"),
        "list_dim": row(r"Median\s*Comparable\s*Listings\s*DIM\s*\(Listings\s*Only\)"),
        "ratio": row(r"Median\s*Sale\s*Price\s*/\s*Median\s*List\s*Price\s*%"),
    }
    periods = ["prior_7_12", "prior_4_6", "current_3"]
    field_map = {
        "sales": "sales", "absorption": "absorption_rate", "active": "active_listings",
        "supply": "months_supply", "close": "median_close_price", "sales_dim": "median_sales_dim",
        "list": "median_list_price", "list_dim": "median_listings_dim",
        "ratio": "median_sale_to_list_price_pct",
    }
    integer_rows = {"sales", "active", "close", "sales_dim", "list", "list_dim"}
    for row_name, tokens in rows.items():
        if len(tokens) < 3:
            continue
        for period, token in zip(periods, tokens):
            token = token.replace("$", "").replace(",", "").replace("%", "")
            try:
                value = int(round(float(token))) if row_name in integer_rows else float(token)
            except ValueError:
                continue
            values[f"{period}_{field_map[row_name]}"] = value
    return values

def parse_1004mc_pdf(file_path: str | Path) -> MarketConditions1004MC:
    """
    Parse or diagnose a 1004MC PDF.

    Direct Crystal Reports PDF download usually has text, but the raw text order
    can be scrambled. Therefore, when a text layer is found, the parser uses a
    coordinate/table strategy instead of trusting plain text order.
    """

    path = Path(file_path)
    result = MarketConditions1004MC(file_path=str(path))

    if not path.exists():
        result.warnings.append("File does not exist.")
        return result

    text, page_count = _extract_pdf_text(path)
    clean = _clean_text(text)

    result.page_count = page_count
    result.total_text_characters = len(clean)
    result.text_found = len(clean) >= 100
    result.image_only = not result.text_found
    result.raw_text_sample = clean[:2500]

    if not result.text_found:
        result.rotated_or_image_form = True
        result.recommended_route = "manual_1004mc_entry_or_ocr"
        result.parser_confidence = "none"
        result.parser_method = "no_text_layer"
        result.warnings.append(
            "No usable text layer was found. This 1004MC PDF appears image-only, scanned, or rotated."
        )
        result.warnings.append(
            "Use manual 1004MC entry now, or regenerate/download the 1004MC as a text-based PDF."
        )
        return result

    if "1004MC" not in clean and "Inventory Analysis" not in clean and "Comparable Sales" not in clean:
        result.recommended_route = "manual_1004mc_entry"
        result.parser_confidence = "low"
        result.parser_method = "not_recognized_as_1004mc"
        result.warnings.append("Text exists, but this does not look like a 1004MC form.")
        return result

    coordinate_result = parse_1004mc_coordinate_table(path)

    if coordinate_result.get("parsed"):
        _apply_values(result, coordinate_result.get("values", {}))
        result.validation = coordinate_result.get("validation", {})
        result.warnings.extend(coordinate_result.get("warnings", []))
        result.parser_method = "pdfplumber_coordinate_table"

        if result.validation.get("inventory_math_ok"):
            result.recommended_route = "parsed_1004mc_coordinate_table"
            result.parser_confidence = "high"
        else:
            result.recommended_route = "manual_review_required"
            result.parser_confidence = "medium"
            result.warnings.append(
                "Values were extracted by coordinates, but validation did not fully pass. Review before use."
            )

        return result

    # Browser "Print PDF" exports often contain the actual report as a full-page
    # raster image plus only browser header/footer text. Try a visual OCR fallback.
    ocr_text, ocr_method = _ocr_pdf_first_page(path)
    ocr_values = _parse_visual_ocr_table(ocr_text) if ocr_text else {}
    core_ocr_keys = {
        f"{period}_{field}"
        for period in ("prior_7_12", "prior_4_6", "current_3")
        for field in (
            "sales",
            "absorption_rate",
            "active_listings",
            "months_supply",
            "median_close_price",
            "median_sales_dim",
        )
    }
    core_table_complete = core_ocr_keys.issubset(ocr_values)

    if core_table_complete:
        _apply_values(result, ocr_values)
        result.validation = _validate_ocr_values(ocr_values)
        result.validation["core_table_complete"] = True
        result.parser_method = ocr_method
        result.raw_text_sample = ocr_text[:2500]
        if result.validation.get("inventory_math_ok"):
            result.recommended_route = "parsed_1004mc_ocr_table"
            result.parser_confidence = "high"
            result.warnings.append("1004MC was read from the visible page image because the embedded text layer did not contain the table.")
        else:
            result.recommended_route = "manual_review_required"
            result.parser_confidence = "medium"
            result.warnings.append("1004MC values were read by OCR, but inventory math requires review.")
        return result

    result.recommended_route = "manual_1004mc_entry_or_ocr"
    result.parser_confidence = "low"
    result.parser_method = ocr_method if ocr_method else "coordinate_parse_failed"
    result.warnings.extend(coordinate_result.get("warnings", []))
    result.warnings.append(
        "The visible 1004MC table could not be read automatically. Use manual entry or install Tesseract OCR."
    )
    return result


def _apply_values(result: MarketConditions1004MC, values: Dict[str, Any]) -> None:
    for key, value in values.items():
        if hasattr(result, key):
            setattr(result, key, value)


def _extract_pdf_text(path: Path) -> tuple[str, Optional[int]]:
    """
    Extract text from a 1004MC PDF.

    The original version required pypdf and crashed on Streamlit Cloud when pypdf
    was not installed. This version tries pypdf first, then falls back to
    pdfplumber so the app can still diagnose or parse text-layer PDFs.
    """

    parts: List[str] = []
    page_count: Optional[int] = None

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        page_count = len(reader.pages)

        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
    except Exception:
        pass

    text = "\n".join(parts).strip()

    if len(text) >= 100:
        return text, page_count

    plumber_parts: List[str] = []

    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            page_count = page_count or len(pdf.pages)

            for page in pdf.pages:
                try:
                    page_text = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=3,
                        layout=False,
                    ) or ""

                    if page_text.strip():
                        plumber_parts.append(page_text)
                        continue

                    words = page.extract_words(
                        x_tolerance=2,
                        y_tolerance=3,
                        keep_blank_chars=False,
                        use_text_flow=False,
                    )

                    word_text = " ".join(
                        word.get("text", "")
                        for word in words
                        if word.get("text")
                    )

                    if word_text.strip():
                        plumber_parts.append(word_text)

                except Exception:
                    continue
    except Exception:
        pass

    fallback_text = "\n".join(plumber_parts).strip()

    if fallback_text:
        return fallback_text, page_count

    return text, page_count


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()

def _validate_ocr_values(values: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Any] = {"inventory_math_ok": True, "periods": {}}
    months_map = {"prior_7_12": 6, "prior_4_6": 3, "current_3": 3}
    for period, months in months_map.items():
        sales = values.get(f"{period}_sales")
        absorption = values.get(f"{period}_absorption_rate")
        active = values.get(f"{period}_active_listings")
        supply = values.get(f"{period}_months_supply")
        period_ok = True
        details: Dict[str, Any] = {}
        if sales is not None and absorption not in (None, 0):
            expected = round(float(sales) / months, 2)
            ok = abs(expected - float(absorption)) <= 0.25
            details["absorption"] = {"expected": expected, "actual": absorption, "ok": ok}
            period_ok = period_ok and ok
        if active is not None and absorption not in (None, 0) and supply is not None:
            expected = round(float(active) / float(absorption), 2)
            ok = abs(expected - float(supply)) <= 0.08
            details["months_supply"] = {"expected": expected, "actual": supply, "ok": ok}
            period_ok = period_ok and ok
        checks["periods"][period] = details
        checks["inventory_math_ok"] = checks["inventory_math_ok"] and period_ok
    return checks
