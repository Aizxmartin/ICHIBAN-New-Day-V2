from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable

import fitz
import pdfplumber

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    from pypdf import PdfReader

from core.address_subject_profile import blank_subject_profile
from core.subject_acquisition.validate_subject_profile import normalize_property_type, validate_subject_profile

# Broad enough for common Colorado subject reports without forcing a city list.
ADDRESS_LINE_RE = re.compile(
    r"\b\d{2,6}\s+[A-Za-z0-9.#'/-]+(?:\s+[A-Za-z0-9.#'/-]+){1,8}(?:,\s*|\s+)(?:[A-Za-z][A-Za-z .'-]+?)(?:,\s*|\s+)(?:CO|Colorado)\s+\d{5}(?:-\d{4})?\b",
    re.IGNORECASE,
)

ZIP_ONLY_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
NUMBER_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")

FIELD_LABEL_ALIASES: dict[str, list[str]] = {
    "subject_address": [
        "Property Address",
        "Subject Address",
        "Address",
        "Situs Address",
        "Property Location",
        "Property",
    ],
    "above_grade_sqft": [
        "Bldg Sq Ft - Above Ground",
        "Above Ground Sq Ft",
        "Above Grade Finished Area",
        "Above Grade Finished Sq Ft",
        "Above Grade Sq Ft",
        "Above Grade Area",
        "Gross Living Area",
        "Living Area",
        "Main Level Sq Ft",
        "Main Level Area",
        "Main Level Living Area",
        "Finished Area Above Grade",
        "Building Area Total",
    ],
    "property_type": [
        "Property Type",
        "Type",
        "Residential Type",
    ],
    "property_subtype": [
        "Property Sub Type",
        "Property Subtype",
        "Sub Type",
        "Style",
    ],
    "beds": ["Beds", "Bedrooms", "Total Bedrooms"],
    "baths": ["Baths", "Bathrooms", "Total Baths", "Bathrooms Total"],
    "year_built": ["Year Built", "Actual Year Built"],
    "real_avm": ["RealAVM", "Real AVM"],
    "real_avm_range": ["RealAVM Range", "Real AVM Range"],
    "basement_sqft": ["Basement", "Basement Sq Ft", "Basement SF", "Basement Area"],
    "finished_basement_sqft": [
        "Finished Basement Sq Ft",
        "Finished Basement SF",
        "Bsmt Finished Area",
        "Finished Basement",
    ],
    "lot_size_sqft": ["Lot Size Sq Ft", "Lot Size", "Lot Sq Ft", "Site Area"],
}

PROPERTY_TYPE_HINTS = {
    "single family residence": "Single Family Residence",
    "single family": "Single Family Residence",
    "residential": "Residential",
    "detached": "Detached",
    "attached": "Attached",
    "townhouse": "Townhouse",
    "townhome": "Townhouse",
    "condominium": "Condominium",
    "condo": "Condominium",
    "duplex": "Duplex",
    "half duplex": "Half Duplex",
    "patio home": "Patio Home",
}


class ExtractionCollector:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.field_sources: dict[str, str] = {}
        self.diagnostics: list[str] = []
        self.source_summary: set[str] = set()

    def set(self, field: str, value: object, source: str) -> None:
        if value in (None, "", []):
            return
        current = self.values.get(field)
        if current not in (None, ""):
            return
        self.values[field] = value
        self.field_sources[field] = source
        self.source_summary.add(source)

    def note(self, message: str) -> None:
        self.diagnostics.append(message)


# ---------- Raw PDF readers ----------

def _read_bytes(uploaded_file: BinaryIO | bytes | str | Path) -> bytes:
    if isinstance(uploaded_file, bytes):
        return uploaded_file
    if isinstance(uploaded_file, (str, Path)):
        return Path(uploaded_file).read_bytes()
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    if hasattr(uploaded_file, "read"):
        data = uploaded_file.read()
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return data
    raise TypeError("Unsupported PDF input type.")



def _extract_pages_with_pymupdf(pdf_bytes: bytes) -> tuple[list[str], list[str]]:
    page_texts: list[str] = []
    block_texts: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_index, page in enumerate(doc, start=1):
            page_texts.append(page.get_text("text") or "")
            blocks = page.get_text("blocks") or []
            for block in sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1))):
                text = (block[4] or "").strip()
                if text:
                    block_texts.append(f"[page {page_index}] {text}")
    return page_texts, block_texts



def _extract_pages_with_pdfplumber(pdf_bytes: bytes) -> list[str]:
    pages: list[str] = []
    with pdfplumber.open(stream=pdf_bytes) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages



def _extract_pages_with_pypdf2(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(BytesIO(pdf_bytes))
    return [page.extract_text() or "" for page in reader.pages]


# ---------- Parsing helpers ----------

def _clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()



def _normalize_address(text: str) -> str:
    text = _clean_space(text.replace(" ,", ",").replace(" , ", ", "))
    text = re.sub(r"\s+,", ",", text)
    return text



def _find_address_candidate(text: str) -> str | None:
    match = ADDRESS_LINE_RE.search(text)
    if match:
        return _normalize_address(match.group(0))
    return None



def _extract_number_from_text(text: str) -> int | float | None:
    match = NUMBER_RE.search(text)
    if not match:
        return None
    cleaned = match.group(1).replace(",", "")
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number



def _find_label_value_same_line(label: str, text: str) -> str | None:
    patterns = [
        rf"{re.escape(label)}\s*[:\-]?\s*([^\n\r|]+)",
        rf"{re.escape(label)}\s+([^\n\r|]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _clean_space(match.group(1))
            if value and value.lower() != label.lower():
                return value
    return None



def _find_value_near_label_in_lines(label_aliases: Iterable[str], lines: list[str]) -> str | None:
    for i, raw_line in enumerate(lines):
        line = _clean_space(raw_line)
        if not line:
            continue
        lowered = line.lower()
        for alias in label_aliases:
            alias_lower = alias.lower()
            if alias_lower in lowered:
                value = _find_label_value_same_line(alias, line)
                if value:
                    return value
                # If the line is mostly label text, use the next non-empty line.
                trailing = line.lower().replace(alias_lower, "").strip(" :-")
                if not trailing:
                    for next_line in lines[i + 1 : i + 4]:
                        candidate = _clean_space(next_line)
                        if candidate and alias_lower not in candidate.lower():
                            return candidate
    return None



def _find_all_text_variants(page_texts: list[str], block_texts: list[str], plumber_pages: list[str], pypdf_pages: list[str]) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []
    if page_texts:
        variants.append(("pymupdf_text", "\n".join(page_texts)))
    if block_texts:
        variants.append(("pymupdf_blocks", "\n".join(block_texts)))
    if plumber_pages:
        variants.append(("pdfplumber_text", "\n".join(plumber_pages)))
    if pypdf_pages:
        variants.append(("pypdf2_text", "\n".join(pypdf_pages)))
    return variants



def _extract_real_avm_range(text: str) -> tuple[int | float | None, int | float | None]:
    patterns = [
        r"Real\s*AVM\s*Range[^\d$]{0,20}\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)",
        r"RealAVM\s*Range[^\d$]{0,20}\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _extract_number_from_text(match.group(1)), _extract_number_from_text(match.group(2))
    return None, None



def _extract_property_type_hint(text: str) -> str | None:
    lowered = text.lower()
    for hint, normalized in PROPERTY_TYPE_HINTS.items():
        if hint in lowered:
            return normalized
    return None



def _extract_fields_from_variant(name: str, text: str, collector: ExtractionCollector) -> None:
    if not text or len(text.strip()) < 20:
        collector.note(f"{name}: no usable text")
        return

    lines = [line for line in text.splitlines() if line.strip()]
    collector.note(f"{name}: extracted {len(text)} characters across {len(lines)} lines")

    if not collector.values.get("subject_address"):
        address = _find_address_candidate(text)
        if not address:
            address = _find_value_near_label_in_lines(FIELD_LABEL_ALIASES["subject_address"], lines)
            if address and not ZIP_ONLY_RE.search(address):
                # Try next line if a label value is too short / vague.
                address = None
        if address:
            collector.set("subject_address", _normalize_address(address), name)

    for numeric_field in [
        "above_grade_sqft",
        "beds",
        "baths",
        "year_built",
        "real_avm",
        "lot_size_sqft",
        "basement_sqft",
        "finished_basement_sqft",
    ]:
        if collector.values.get(numeric_field) not in (None, ""):
            continue
        raw_value = _find_value_near_label_in_lines(FIELD_LABEL_ALIASES[numeric_field], lines)
        number = _extract_number_from_text(raw_value or "") if raw_value else None
        if number is not None:
            collector.set(numeric_field, number, name)

    if collector.values.get("real_avm_range_low") in (None, "") or collector.values.get("real_avm_range_high") in (None, ""):
        low, high = _extract_real_avm_range(text)
        if low is not None:
            collector.set("real_avm_range_low", low, name)
        if high is not None:
            collector.set("real_avm_range_high", high, name)

    if not collector.values.get("property_type"):
        raw_type = _find_value_near_label_in_lines(FIELD_LABEL_ALIASES["property_type"], lines)
        normalized = normalize_property_type(raw_type) if raw_type else None
        if not normalized:
            normalized = _extract_property_type_hint(text)
        if normalized:
            collector.set("property_type", normalized, name)

    if not collector.values.get("property_subtype"):
        raw_subtype = _find_value_near_label_in_lines(FIELD_LABEL_ALIASES["property_subtype"], lines)
        if raw_subtype:
            collector.set("property_subtype", raw_subtype.title(), name)



def extract_subject_from_pdf(uploaded_file: BinaryIO | bytes | str | Path, fallback_address: str | None = None) -> dict:
    pdf_bytes = _read_bytes(uploaded_file)
    page_texts, block_texts = [], []
    plumber_pages, pypdf_pages = [], []

    collector = ExtractionCollector()

    try:
        page_texts, block_texts = _extract_pages_with_pymupdf(pdf_bytes)
    except Exception as exc:
        collector.note(f"pymupdf failed: {exc}")

    try:
        plumber_pages = _extract_pages_with_pdfplumber(pdf_bytes)
    except Exception as exc:
        collector.note(f"pdfplumber failed: {exc}")

    try:
        pypdf_pages = _extract_pages_with_pypdf2(pdf_bytes)
    except Exception as exc:
        collector.note(f"pypdf2 failed: {exc}")

    variants = _find_all_text_variants(page_texts, block_texts, plumber_pages, pypdf_pages)
    for name, text in variants:
        _extract_fields_from_variant(name, text, collector)

    draft = blank_subject_profile(fallback_address or "")
    draft["subject_acquisition_status"] = "pdf_attempted"
    draft["source_summary"] = sorted(collector.source_summary) or ["subject_pdf"]
    draft["field_sources"] = collector.field_sources
    draft.update(collector.values)

    combined_text = "\n\n".join(text for _, text in variants)
    draft["pdf_extraction_diagnostics"] = collector.diagnostics
    draft["raw_pdf_text_excerpt"] = combined_text[:6000]

    validated = validate_subject_profile(draft)
    validated["pdf_extraction_diagnostics"] = collector.diagnostics
    validated["raw_pdf_text_excerpt"] = combined_text[:6000]
    validated["subject_acquisition_status"] = (
        "locked_from_pdf" if validated.get("subject_profile_ready") else "pdf_needs_backup_or_manual"
    )
    if not validated.get("source_summary"):
        validated["source_summary"] = sorted(collector.source_summary) or ["subject_pdf"]
    if not validated.get("field_sources"):
        validated["field_sources"] = collector.field_sources
    return validated
