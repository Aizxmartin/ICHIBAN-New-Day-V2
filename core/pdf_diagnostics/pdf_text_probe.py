from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def probe_pdf_text(file_path: str | Path, max_pages: int = 5) -> Dict[str, Any]:
    """
    Basic text extraction probe.

    Tries pypdf first because it is lightweight and commonly available.
    Falls back gracefully if the package is missing or the PDF is unreadable.

    This module should not make final field decisions.
    It only answers: "Does this PDF contain extractable text?"
    """

    path = Path(file_path)
    result: Dict[str, Any] = {
        "method": "pypdf",
        "text_found": False,
        "page_count": None,
        "pages_checked": 0,
        "total_text_characters": 0,
        "text_sample": "",
        "errors": [],
    }

    try:
        from pypdf import PdfReader
    except Exception as exc:
        result["errors"].append(
            f"pypdf is not installed or could not be imported: {exc}"
        )
        return result

    try:
        reader = PdfReader(str(path))
        result["page_count"] = len(reader.pages)

        samples: List[str] = []
        pages_to_check = min(len(reader.pages), max_pages)

        for index in range(pages_to_check):
            result["pages_checked"] += 1
            try:
                text = reader.pages[index].extract_text() or ""
                if text.strip():
                    samples.append(text.strip())
            except Exception as exc:
                result["errors"].append(f"Page {index + 1} text extraction failed: {exc}")

        combined_text = "\n".join(samples)
        result["total_text_characters"] = len(combined_text)
        result["text_found"] = len(combined_text.strip()) >= 50
        result["text_sample"] = _clean_sample(combined_text, limit=1500)

    except Exception as exc:
        result["errors"].append(f"PDF could not be read by pypdf: {exc}")

    return result


def _clean_sample(text: str, limit: int = 1500) -> str:
    cleaned = " ".join(text.replace("\x00", " ").split())
    return cleaned[:limit]
