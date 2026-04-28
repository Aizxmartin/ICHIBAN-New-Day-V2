from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_OUTPUT_DIR = Path("data")
DEFAULT_SUBJECT_FILE = DEFAULT_OUTPUT_DIR / "verified_subject.json"


def save_verified_subject(
    subject_data: Dict[str, Any],
    output_path: Optional[str | Path] = None,
) -> Path:
    """
    Save the user-confirmed subject facts after the verification screen.

    This should be called only after the agent/user reviews and confirms
    the extracted subject facts.
    """

    save_path = Path(output_path) if output_path else DEFAULT_SUBJECT_FILE
    save_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_data = dict(subject_data)
    cleaned_data["subject_verified"] = True

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2)

    return save_path


def load_verified_subject(
    input_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load the verified subject facts if they exist.
    Returns None if no verified subject file exists.
    """

    load_path = Path(input_path) if input_path else DEFAULT_SUBJECT_FILE

    if not load_path.exists():
        return None

    with open(load_path, "r", encoding="utf-8") as f:
        return json.load(f)


def subject_is_verified(
    input_path: Optional[str | Path] = None,
) -> bool:
    """
    Check whether the verified subject file exists and is marked verified.
    """

    subject_data = load_verified_subject(input_path)

    if not subject_data:
        return False

    return bool(subject_data.get("subject_verified"))


def clear_verified_subject(
    input_path: Optional[str | Path] = None,
) -> bool:
    """
    Delete the verified subject file.

    Useful when starting a new valuation or replacing the subject property.
    Returns True if a file was deleted.
    """

    delete_path = Path(input_path) if input_path else DEFAULT_SUBJECT_FILE

    if delete_path.exists():
        delete_path.unlink()
        return True

    return False