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
SUPPLEMENTAL_RULES_FILE_NAME = "ICHIBAN_GPT_Supplemental_Rules_v1.json"


def get_repo_root() -> Path:
    """Return the local repository root based on this file location."""
    # core/governance/load_governance.py -> core/governance -> core -> repo root
    return Path(__file__).resolve().parents[2]


def get_default_governance_path() -> Path:
    """Return the expected path for the report-governance JSON file."""
    return get_repo_root() / "core" / "governance" / REPORT_GOVERNANCE_FILE_NAME


def get_default_supplemental_rules_path() -> Path:
    """Return the expected path for the supplemental GPT rules JSON file."""
    return get_repo_root() / "core" / "governance" / SUPPLEMENTAL_RULES_FILE_NAME


def _load_json_object(path: Path, description: str) -> Dict[str, Any]:
    """Load a JSON object and validate that it is a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"{description} was not found. Expected location: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{description} must contain a JSON object: {path}")

    return data


def load_report_governance(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load the ICHIBAN report governance JSON.

    The app should call this immediately before building the GPT report prompt.
    This keeps the mini API focused on the approved ICHIBAN reporting rules.

    Supplemental GPT rules are loaded when present. They are intentionally
    separate from the main governance file so Buyer Considerations and report
    priority-filter rules can evolve without touching valuation math.
    """
    governance_path = Path(path) if path else get_default_governance_path()
    data = _load_json_object(governance_path, "ICHIBAN report governance JSON")

    supplemental_path = get_default_supplemental_rules_path()
    if supplemental_path.exists():
        data["supplemental_gpt_rules"] = _load_json_object(
            supplemental_path,
            "ICHIBAN supplemental GPT rules JSON",
        )
    else:
        data["supplemental_gpt_rules"] = {
            "loaded": False,
            "note": f"Optional supplemental GPT rules file not found at {supplemental_path}",
        }

    return data
