from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.market_conditions import parse_1004mc_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse or diagnose a 1004MC PDF.")
    parser.add_argument("file", help="Path to 1004MC PDF.")
    args = parser.parse_args()

    result = parse_1004mc_pdf(Path(args.file))
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
