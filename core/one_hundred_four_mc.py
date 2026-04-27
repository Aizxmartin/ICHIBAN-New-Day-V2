"""
ICHIBAN 1004MC / market-trend intake helpers.

Purpose:
- Accept an optional uploaded 1004MC / market trend report.
- Accept optional manual override values.
- Store only structured results needed by the valuation/report workflow.
- Do not retain the raw uploaded file or full extracted text in session state.

This module intentionally keeps parsing conservative. If a report format cannot be
reliably parsed, the UI should allow manual annual/monthly rate entry and proceed
without blocking valuation.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, Optional

import pandas as pd


TREND_VALUES = {"increasing", "stable", "declining", "insufficient", "not_supplied"}


def _clean_percent(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip().replace("%", "").replace(",", "")
        if text == "":
            return None
        return float(text)
    except Exception:
        return None


def _normalize_trend(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip().lower().replace(" ", "_")
    aliases = {
        "increase": "increasing",
        "increasing_market": "increasing",
        "up": "increasing",
        "appreciating": "increasing",
        "stable_market": "stable",
        "flat": "stable",
        "balanced": "stable",
        "decline": "declining",
        "declining_market": "declining",
        "down": "declining",
        "depreciating": "declining",
        "insufficient_data": "insufficient",
        "not_available": "not_supplied",
        "none": "not_supplied",
    }
    text = aliases.get(text, text)
    return text if text in TREND_VALUES else None


def _infer_trend(annual_percent: Optional[float], monthly_percent: Optional[float]) -> str:
    basis = annual_percent
    if basis is None and monthly_percent is not None:
        basis = monthly_percent * 12
    if basis is None:
        return "not_supplied"
    if basis > 0.5:
        return "increasing"
    if basis < -0.5:
        return "declining"
    return "stable"


def _extract_text_from_pdf(data: bytes) -> str:
    notes = []
    text_parts = []

    # pdfplumber tends to handle table-like PDFs better when available.
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:6]:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            return "\n".join(text_parts)
    except Exception as exc:  # pragma: no cover - best-effort fallback
        notes.append(str(exc))

    # PyPDF2 fallback.
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages[:6]:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    except Exception:
        pass

    return "\n".join(text_parts)


def _extract_text_from_spreadsheet(data: bytes, suffix: str) -> str:
    try:
        if suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
            frames = []
            for name, df in list(sheets.items())[:4]:
                frames.append(f"SHEET: {name}\n" + df.astype(str).head(80).to_csv(index=False, header=False))
            return "\n".join(frames)
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(data), header=None, encoding_errors="ignore")
            return df.astype(str).head(120).to_csv(index=False, header=False)
    except Exception:
        return ""
    return ""


def _extract_text(uploaded_file: Any) -> tuple[str, Dict[str, Any]]:
    if uploaded_file is None:
        return "", {"file_uploaded": False}

    name = getattr(uploaded_file, "name", "uploaded_1004mc") or "uploaded_1004mc"
    suffix = "." + name.lower().rsplit(".", 1)[-1] if "." in name else ""

    try:
        data = uploaded_file.getvalue()
    except Exception:
        data = uploaded_file.read()

    metadata = {
        "file_uploaded": True,
        "file_name": name,
        "file_type": suffix.replace(".", "") or None,
        "raw_file_retained_in_session": False,
        "bytes_received": len(data or b""),
    }

    if not data:
        return "", metadata

    if suffix == ".pdf":
        return _extract_text_from_pdf(data), metadata
    if suffix in {".xlsx", ".xls", ".csv"}:
        return _extract_text_from_spreadsheet(data, suffix), metadata
    if suffix in {".txt", ".text"}:
        try:
            return data.decode("utf-8", errors="ignore"), metadata
        except Exception:
            return "", metadata

    return "", metadata


def _find_percent_near_keywords(text: str, keywords: list[str]) -> Optional[float]:
    if not text:
        return None

    compact = re.sub(r"\s+", " ", text)
    percent_pattern = r"[-+]?\d{1,3}(?:\.\d+)?\s*%"

    for keyword in keywords:
        # Look after the keyword first.
        pattern = rf"{keyword}.{{0,120}}?({percent_pattern})"
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            return _clean_percent(match.group(1))

        # Some forms put the percentage before the label.
        pattern = rf"({percent_pattern}).{{0,120}}?{keyword}"
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            return _clean_percent(match.group(1))

    return None


def _parse_rates_from_text(text: str) -> Dict[str, Any]:
    if not text.strip():
        return {
            "annual_market_change_percent": None,
            "monthly_market_change_percent": None,
            "market_trend_classification": "not_supplied",
            "parse_confidence": "none",
            "parse_notes": ["No readable 1004MC text was extracted."],
        }

    annual = _find_percent_near_keywords(
        text,
        [
            r"annual(?:ized)?\s+(?:market\s+)?(?:change|trend|rate)",
            r"12[-\s]?month\s+(?:market\s+)?(?:change|trend|rate)",
            r"year(?:ly|\s+over\s+year)?\s+(?:change|trend|rate)",
        ],
    )
    monthly = _find_percent_near_keywords(
        text,
        [
            r"monthly\s+(?:market\s+)?(?:change|trend|rate)",
            r"month\s+(?:over\s+month\s+)?(?:change|trend|rate)",
        ],
    )

    lower = text.lower()
    trend = None
    if "declining" in lower or "decline" in lower or "decreasing" in lower:
        trend = "declining"
    elif "increasing" in lower or "increase" in lower or "appreciat" in lower:
        trend = "increasing"
    elif "stable" in lower or "balanced" in lower or "unchanged" in lower:
        trend = "stable"

    if annual is not None and monthly is None:
        monthly = annual / 12.0
        monthly_derived = True
    else:
        monthly_derived = False

    if annual is None and monthly is not None:
        annual = monthly * 12.0
        annual_derived = True
    else:
        annual_derived = False

    trend = trend or _infer_trend(annual, monthly)
    confidence = "low"
    if annual is not None and monthly is not None:
        confidence = "medium"
    if annual is not None and monthly is not None and trend in {"increasing", "stable", "declining"}:
        confidence = "medium"

    notes = []
    if monthly_derived:
        notes.append("Monthly rate derived by dividing annual rate by 12.")
    if annual_derived:
        notes.append("Annual rate derived by multiplying monthly rate by 12.")
    if annual is None and monthly is None:
        notes.append("No annual or monthly percentage was confidently parsed from the uploaded file.")

    return {
        "annual_market_change_percent": annual,
        "monthly_market_change_percent": monthly,
        "market_trend_classification": trend,
        "parse_confidence": confidence,
        "parse_notes": notes,
    }


def build_1004mc_summary(
    uploaded_file: Any = None,
    manual_annual_percent: Any = None,
    manual_monthly_percent: Any = None,
    manual_trend: Any = None,
    manual_note: str = "",
) -> Dict[str, Any]:
    """
    Return a structured 1004MC handoff for session_state and reporting.

    Manual values override parser values. Missing 1004MC data is acceptable and
    should not block the valuation workflow.
    """
    text, file_meta = _extract_text(uploaded_file)
    parsed = _parse_rates_from_text(text)

    manual_annual = _clean_percent(manual_annual_percent)
    manual_monthly = _clean_percent(manual_monthly_percent)
    manual_trend_clean = _normalize_trend(manual_trend)

    annual = manual_annual if manual_annual is not None else parsed.get("annual_market_change_percent")
    monthly = manual_monthly if manual_monthly is not None else parsed.get("monthly_market_change_percent")

    derived_notes = []
    if annual is not None and monthly is None:
        monthly = annual / 12.0
        derived_notes.append("Monthly rate derived from supplied annual rate.")
    if monthly is not None and annual is None:
        annual = monthly * 12.0
        derived_notes.append("Annual rate derived from supplied monthly rate.")

    trend = manual_trend_clean or parsed.get("market_trend_classification") or _infer_trend(annual, monthly)
    if trend in {None, "not_supplied"}:
        trend = _infer_trend(annual, monthly)

    supplied = bool(file_meta.get("file_uploaded") or manual_annual is not None or manual_monthly is not None or manual_trend_clean)
    source_status = "not_supplied"
    if file_meta.get("file_uploaded") and any(v is not None for v in [manual_annual, manual_monthly, manual_trend_clean]):
        source_status = "file_plus_manual_entry"
    elif file_meta.get("file_uploaded"):
        source_status = "file_uploaded"
    elif supplied:
        source_status = "manual_entry"

    time_supported = bool(monthly is not None and trend in {"increasing", "stable", "declining"})

    return {
        "source_status": source_status,
        "is_supplied": supplied,
        "file_metadata": file_meta,
        "annual_market_change_percent": annual,
        "monthly_market_change_percent": monthly,
        "market_trend_classification": trend,
        "time_adjustments_supported": time_supported,
        "time_adjustment_policy": "Use monthly_market_change_percent for comp time adjustments only after the local valuation engine applies the rule. GPT may explain but must not calculate missing time adjustments.",
        "manual_note": manual_note.strip() if manual_note else "",
        "parser_summary": {
            "parse_confidence": parsed.get("parse_confidence"),
            "parse_notes": (parsed.get("parse_notes") or []) + derived_notes,
            "text_excerpt_retained": False,
        },
    }
