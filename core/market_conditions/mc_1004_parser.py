from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

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

    result.recommended_route = "manual_1004mc_entry"
    result.parser_confidence = "low"
    result.parser_method = "coordinate_parse_failed"
    result.warnings.extend(coordinate_result.get("warnings", []))
    result.warnings.append(
        "Text layer exists, but the 1004MC table could not be safely parsed by coordinates."
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