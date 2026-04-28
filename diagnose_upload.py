from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.pdf_diagnostics import probe_document_source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose an uploaded ICHIBAN subject/market/AVM document."
    )
    parser.add_argument("file", help="Path to PDF, XPS, or OXPS file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON diagnostic output.",
    )
    args = parser.parse_args()

    result = probe_document_source(Path(args.file))

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    print("\nICHIBAN Document Diagnostic")
    print("-" * 32)
    print(f"File: {result.file_name}")
    print(f"Type: {result.file_type}")
    print(f"Likely source: {result.likely_source}")
    print(f"Category: {result.document_category}")
    print(f"Recommended parser: {result.recommended_parser}")
    print(f"Manual fallback required: {result.manual_fallback_required}")
    print(f"Text found: {result.text_found}")
    print(f"Coordinate text available: {result.coordinate_text_available}")
    print(f"XPS glyph text available: {result.xps_glyph_text_available}")
    print(f"Image only: {result.image_only}")
    print(f"Confidence: {result.confidence}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f" - {warning}")

    if result.extracted_text_sample:
        print("\nText sample:")
        print(result.extracted_text_sample[:700])


if __name__ == "__main__":
    main()
