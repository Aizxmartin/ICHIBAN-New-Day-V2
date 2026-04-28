from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pdf_text_probe import probe_pdf_text
from .pdf_layout_probe import probe_pdf_layout
from .xps_probe import probe_xps


@dataclass
class DiagnosticResult:
    """
    Standard diagnostic output consumed by Streamlit intake and downstream parsers.

    The valuation engine should not run directly against raw uploads.
    It should run only after this diagnostic layer classifies the file and
    subject facts are verified.
    """

    file_path: str
    file_name: str
    file_extension: str

    file_type: str = "unknown"

    text_found: bool = False
    image_only: bool = False
    coordinate_text_available: bool = False
    xps_glyph_text_available: bool = False

    estimated_page_count: Optional[int] = None
    extracted_text_sample: str = ""

    likely_source: str = "unknown"
    document_category: str = "unknown"

    recommended_parser: str = "manual_subject_entry"
    manual_fallback_required: bool = True

    confidence: str = "low"
    warnings: List[str] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def probe_document_source(file_path: str | Path) -> DiagnosticResult:
    """
    Classify an uploaded file before extraction.

    Categories:
        A: searchable_pdf_clean_text
        B: searchable_pdf_coordinate_layout
        C: xps_oxps_glyph_text
        D: image_only_pdf
        E: unknown_or_manual_fallback

    Recommended parsers are intentionally named as future routing targets.
    They do not all need to exist yet.
    """

    path = Path(file_path)
    extension = path.suffix.lower().replace(".", "")

    result = DiagnosticResult(
        file_path=str(path),
        file_name=path.name,
        file_extension=extension,
        file_type=_guess_file_type(extension),
    )

    if not path.exists():
        result.warnings.append("File does not exist.")
        result.document_category = "E_unknown_or_manual_fallback"
        result.recommended_parser = "manual_subject_entry"
        return result

    if extension == "pdf":
        return _probe_pdf(path, result)

    if extension in {"xps", "oxps"}:
        return _probe_xps_or_oxps(path, result)

    result.warnings.append(f"Unsupported file extension: .{extension}")
    result.document_category = "E_unknown_or_manual_fallback"
    result.recommended_parser = "manual_subject_entry"
    return result


def _probe_pdf(path: Path, result: DiagnosticResult) -> DiagnosticResult:
    text_probe = probe_pdf_text(path)
    layout_probe = probe_pdf_layout(path)

    result.debug["pdf_text_probe"] = text_probe
    result.debug["pdf_layout_probe"] = layout_probe

    result.text_found = bool(text_probe.get("text_found"))
    result.estimated_page_count = text_probe.get("page_count") or layout_probe.get("page_count")
    result.extracted_text_sample = text_probe.get("text_sample", "")

    result.coordinate_text_available = bool(layout_probe.get("coordinate_text_available"))

    # Heuristic: if text extraction finds almost nothing, assume image-only.
    char_count = int(text_probe.get("total_text_characters") or 0)
    result.image_only = char_count < 50 and not result.coordinate_text_available

    # Detect likely report source from available text.
    combined_sample = (
        (text_probe.get("text_sample") or "") + " " +
        (layout_probe.get("layout_text_sample") or "")
    ).lower()

    result.likely_source = _infer_likely_source(combined_sample)

    if result.text_found and char_count >= 500:
        if result.likely_source == "realist_corelogic":
            result.document_category = "B_searchable_pdf_coordinate_layout"
            result.recommended_parser = "realist_pdf_coordinate_parser"
            result.manual_fallback_required = False
            result.confidence = "medium"
            return result

        if result.coordinate_text_available:
            result.document_category = "B_searchable_pdf_coordinate_layout"
            result.recommended_parser = "generic_pdf_coordinate_parser"
            result.manual_fallback_required = False
            result.confidence = "medium"
            return result

        result.document_category = "A_searchable_pdf_clean_text"
        result.recommended_parser = "generic_pdf_text_parser"
        result.manual_fallback_required = False
        result.confidence = "medium"
        return result

    if result.coordinate_text_available:
        result.document_category = "B_searchable_pdf_coordinate_layout"
        result.recommended_parser = "generic_pdf_coordinate_parser"
        result.manual_fallback_required = False
        result.confidence = "low"
        result.warnings.append("Coordinate text was detected, but normal text extraction was weak.")
        return result

    if result.image_only:
        result.document_category = "D_image_only_pdf"
        result.recommended_parser = "image_ocr_or_manual_subject_entry"
        result.manual_fallback_required = True
        result.confidence = "medium"
        result.warnings.append("PDF appears to be image-only or nearly image-only.")
        return result

    result.document_category = "E_unknown_or_manual_fallback"
    result.recommended_parser = "manual_subject_entry"
    result.manual_fallback_required = True
    result.warnings.append("Could not confidently classify PDF.")
    return result


def _probe_xps_or_oxps(path: Path, result: DiagnosticResult) -> DiagnosticResult:
    xps_result = probe_xps(path)

    result.debug["xps_probe"] = xps_result
    result.xps_glyph_text_available = bool(xps_result.get("glyph_text_available"))
    result.text_found = result.xps_glyph_text_available
    result.extracted_text_sample = xps_result.get("text_sample", "")
    result.estimated_page_count = xps_result.get("estimated_page_count")
    result.likely_source = _infer_likely_source(result.extracted_text_sample.lower())

    if result.xps_glyph_text_available:
        result.document_category = "C_xps_oxps_glyph_text"
        result.recommended_parser = "xps_glyph_parser"
        result.manual_fallback_required = False
        result.confidence = "medium"
        return result

    result.document_category = "E_unknown_or_manual_fallback"
    result.recommended_parser = "manual_subject_entry"
    result.manual_fallback_required = True
    result.confidence = "low"
    result.warnings.append("XPS/OXPS file did not expose readable glyph text.")
    return result


def _guess_file_type(extension: str) -> str:
    if extension == "pdf":
        return "pdf"
    if extension in {"xps", "oxps"}:
        return "xps_oxps"
    return "unknown"


def _infer_likely_source(text: str) -> str:
    """
    Light heuristic only. Do not use this as final extraction logic.
    """

    if any(term in text for term in [
        "realist",
        "corelogic",
        "realavm",
        "property detail report",
        "tax information",
        "bldg sq ft",
    ]):
        return "realist_corelogic"

    if any(term in text for term in [
        "zestimate",
        "zillow",
        "rent zestimate",
    ]):
        return "zillow"

    if any(term in text for term in [
        "redfin estimate",
        "redfin",
    ]):
        return "redfin"

    if any(term in text for term in [
        "1004mc",
        "market conditions addendum",
        "absorption rate",
        "overall trend",
    ]):
        return "1004mc_market_conditions"

    if any(term in text for term in [
        "recolorado",
        "mls #",
        "listing id",
        "close price",
        "days in mls",
    ]):
        return "mls_export_or_report"

    return "unknown"
