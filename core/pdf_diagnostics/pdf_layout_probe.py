from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def probe_pdf_layout(file_path: str | Path, max_pages: int = 3) -> Dict[str, Any]:
    """
    Coordinate/layout text probe.

    Uses pdfplumber if available. Realist/CoreLogic and 1004MC reports may
    have useful text coordinates even when plain text order is not ideal.

    This does not extract final fields. It only determines whether coordinate
    text exists and gives a sample for routing.
    """

    path = Path(file_path)
    result: Dict[str, Any] = {
        "method": "pdfplumber",
        "coordinate_text_available": False,
        "page_count": None,
        "pages_checked": 0,
        "word_count": 0,
        "layout_text_sample": "",
        "errors": [],
    }

    try:
        import pdfplumber
    except Exception as exc:
        result["errors"].append(
            f"pdfplumber is not installed or could not be imported: {exc}"
        )
        return result

    try:
        words_collected: List[str] = []

        with pdfplumber.open(str(path)) as pdf:
            result["page_count"] = len(pdf.pages)
            pages_to_check = min(len(pdf.pages), max_pages)

            for index in range(pages_to_check):
                result["pages_checked"] += 1
                page = pdf.pages[index]

                try:
                    words = page.extract_words(
                        x_tolerance=2,
                        y_tolerance=3,
                        keep_blank_chars=False,
                        use_text_flow=False,
                    )
                    result["word_count"] += len(words)

                    for word in words[:300]:
                        text = word.get("text", "")
                        if text:
                            words_collected.append(text)

                except Exception as exc:
                    result["errors"].append(f"Page {index + 1} layout extraction failed: {exc}")

        result["coordinate_text_available"] = result["word_count"] >= 10
        result["layout_text_sample"] = _clean_sample(" ".join(words_collected), limit=1500)

    except Exception as exc:
        result["errors"].append(f"PDF could not be read by pdfplumber: {exc}")

    return result


def _clean_sample(text: str, limit: int = 1500) -> str:
    cleaned = " ".join(text.replace("\x00", " ").split())
    return cleaned[:limit]
