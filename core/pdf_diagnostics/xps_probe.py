from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET
import zipfile


def probe_xps(file_path: str | Path, max_fixed_pages: int = 5) -> Dict[str, Any]:
    """
    Probe XPS/OXPS packages for Glyphs UnicodeString text.

    XPS/OXPS files are often ZIP-like packages containing XML page documents.
    Text may appear in Glyphs elements using a UnicodeString attribute.

    This is experimental but important for the ICHIBAN pre-API strategy.
    """

    path = Path(file_path)
    result: Dict[str, Any] = {
        "method": "xps_zip_xml_glyph_probe",
        "glyph_text_available": False,
        "estimated_page_count": None,
        "glyph_count": 0,
        "text_sample": "",
        "errors": [],
    }

    if not zipfile.is_zipfile(path):
        result["errors"].append("File is not a ZIP-like XPS/OXPS package.")
        return result

    try:
        samples: List[str] = []

        with zipfile.ZipFile(path, "r") as zf:
            fixed_pages = [
                name for name in zf.namelist()
                if name.lower().endswith(".fpage")
                or "fixedpage" in name.lower()
                or name.lower().endswith(".xml")
            ]

            result["estimated_page_count"] = len([
                name for name in fixed_pages
                if name.lower().endswith(".fpage") or "fixedpage" in name.lower()
            ]) or None

            for name in fixed_pages[:max_fixed_pages]:
                try:
                    xml_bytes = zf.read(name)
                    page_texts = _extract_glyph_text_from_xml(xml_bytes)
                    result["glyph_count"] += len(page_texts)
                    samples.extend(page_texts)
                except Exception as exc:
                    result["errors"].append(f"Could not parse {name}: {exc}")

        combined = " ".join(samples)
        result["glyph_text_available"] = len(combined.strip()) >= 50
        result["text_sample"] = _clean_sample(combined, limit=1500)

    except Exception as exc:
        result["errors"].append(f"XPS/OXPS package could not be read: {exc}")

    return result


def _extract_glyph_text_from_xml(xml_bytes: bytes) -> List[str]:
    texts: List[str] = []

    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return texts

    for element in root.iter():
        # Namespace-safe element ending check.
        if element.tag.lower().endswith("glyphs"):
            unicode_string = element.attrib.get("UnicodeString")
            if unicode_string:
                texts.append(unicode_string)

    return texts


def _clean_sample(text: str, limit: int = 1500) -> str:
    cleaned = " ".join(text.replace("\x00", " ").split())
    return cleaned[:limit]
