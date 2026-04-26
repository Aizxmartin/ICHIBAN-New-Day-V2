"""
ICHIBAN governance loader.

This module keeps the final-report rules in the private logic layer and
loads them only when the GPT report writer is called.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union


REPORT_GOVERNANCE_FILE_NAME = "ICHIBAN_Insight_Report_Governance_v2.json"


def get_repo_root() -> Path:
    """Return the local repository root based on this file location."""
    # core/governance/load_governance.py -> core/governance -> core -> repo root
    return Path(__file__).resolve().parents[2]


def get_default_governance_path() -> Path:
    """Return the expected path for the report-governance JSON file."""
    return get_repo_root() / "core" / "governance" / REPORT_GOVERNANCE_FILE_NAME


def load_report_governance(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load the ICHIBAN report governance JSON.

    The app should call this immediately before building the GPT report prompt.
    This keeps the mini API focused on the approved ICHIBAN reporting rules.
    """
    governance_path = Path(path) if path else get_default_governance_path()

    if not governance_path.exists():
        raise FileNotFoundError(
            "ICHIBAN report governance JSON was not found.\n"
            f"Expected location: {governance_path}\n"
            "Create the folder core/governance/ and place "
            f"{REPORT_GOVERNANCE_FILE_NAME} there."
        )

    with governance_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Governance file must contain a JSON object: {governance_path}")

    return data
