from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.subject_acquisition import parse_realist_subject


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse core subject facts from a Realist/CoreLogic PDF."
    )
    parser.add_argument("file", help="Path to Realist/CoreLogic PDF file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON parser output.",
    )
    args = parser.parse_args()

    facts = parse_realist_subject(Path(args.file))

    if args.json:
        print(json.dumps(facts.to_dict(), indent=2))
        return

    print("\nICHIBAN Realist Subject Parser")
    print("-" * 32)
    print(f"Address: {facts.full_address}")
    print(f"County: {facts.county}")
    print(f"APN: {facts.apn}")
    print(f"CLIP: {facts.clip}")
    print(f"Schedule Number: {facts.schedule_number}")
    print(f"Sale Price: {facts.sale_price}")
    print(f"Sale Date: {facts.sale_date}")
    print(f"Building Sq Ft: {facts.building_sqft}")
    print(f"Lot Sq Ft: {facts.lot_sqft}")
    print(f"Year Built: {facts.year_built}")
    print(f"Type: {facts.property_type}")
    print(f"Owner: {facts.owner_name}")
    print(f"Neighborhood: {facts.neighborhood_name}")
    print(f"Subdivision: {facts.subdivision}")
    print(f"Zoning: {facts.zoning}")
    print(f"RealAVM: {facts.real_avm}")
    print(f"Confidence: {facts.confidence}")

    if facts.warnings:
        print("\nWarnings:")
        for warning in facts.warnings:
            print(f" - {warning}")


if __name__ == "__main__":
    main()
