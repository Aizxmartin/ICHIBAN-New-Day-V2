from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_OUTPUT_DIR = Path("data")
DEFAULT_1004MC_FILE = DEFAULT_OUTPUT_DIR / "verified_1004mc.json"


def save_verified_1004mc(
    market_data: Dict[str, Any],
    output_path: Optional[str | Path] = None,
) -> Path:
    """
    Save verified 1004MC / time-trend evidence after parser review or manual entry.

    This should be called only after the agent/user reviews the parsed or manual values.
    """

    save_path = Path(output_path) if output_path else DEFAULT_1004MC_FILE
    save_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_data = dict(market_data)
    cleaned_data["market_conditions_verified"] = True

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2)

    return save_path


def load_verified_1004mc(
    input_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load verified 1004MC / time-trend evidence if it exists.
    Returns None if no verified file exists.
    """

    load_path = Path(input_path) if input_path else DEFAULT_1004MC_FILE

    if not load_path.exists():
        return None

    with open(load_path, "r", encoding="utf-8") as f:
        return json.load(f)


def market_conditions_are_verified(
    input_path: Optional[str | Path] = None,
) -> bool:
    """
    Check whether verified 1004MC / market conditions data exists.
    """

    data = load_verified_1004mc(input_path)

    if not data:
        return False

    return bool(data.get("market_conditions_verified"))


def clear_verified_1004mc(
    input_path: Optional[str | Path] = None,
) -> bool:
    """
    Delete verified 1004MC / market conditions data.
    Returns True if a file was deleted.
    """

    delete_path = Path(input_path) if input_path else DEFAULT_1004MC_FILE

    if delete_path.exists():
        delete_path.unlink()
        return True

    return False
