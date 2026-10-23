from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.pdf_diagnostics import probe_document_source
from core.subject_acquisition import parse_realist_subject


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run document diagnostics, then parse Realist subject facts when appropriate."
    )
    parser.add_argument("file", help="Path to PDF, XPS, or OXPS file.")
    args = parser.parse_args()

    diagnostic = probe_document_source(Path(args.file))

    output = {
        "diagnostic": diagnostic.to_dict(),
        "subject_facts": None,
    }

    if diagnostic.recommended_parser == "realist_pdf_coordinate_parser":
        output["subject_facts"] = parse_realist_subject(Path(args.file)).to_dict()
    else:
        output["subject_facts"] = {
            "manual_fallback_required": True,
            "reason": f"Recommended parser is {diagnostic.recommended_parser}, not realist_pdf_coordinate_parser.",
        }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
