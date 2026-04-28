from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def probe_image_or_image_pdf(file_path: str | Path) -> Dict[str, Any]:
    """
    Placeholder for later OCR probing.

    We are intentionally NOT making OCR the first solution.
    OCR should be a last-resort fallback for image-only PDFs or screenshots.

    Future options:
        - Render first PDF page to image
        - Detect whether there is meaningful text-like structure
        - Optionally run OCR only on likely AVM/subject-value regions
    """

    return {
        "method": "ocr_placeholder",
        "ocr_attempted": False,
        "recommended_next_step": "manual_subject_entry_or_targeted_ocr",
        "notes": [
            "OCR should remain a fallback, not the primary Realist/CoreLogic path.",
            "Prefer source-layer capture, searchable PDF, coordinate text, or XPS/OXPS glyph text first.",
        ],
    }
