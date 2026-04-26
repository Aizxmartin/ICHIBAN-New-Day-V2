"""
Builds the structured ICHIBAN payload sent to the GPT report writer.

Important design rule:
- Python/local app owns deterministic math and field organization.
- Mini GPT owns narrative explanation only.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional


def _json_safe(value: Any) -> Any:
    """Convert common non-JSON values into plain Python-safe values."""
    if value is None:
        return None

    # Pandas / NumPy scalars often expose item().
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    # Avoid trying to serialize large dataframes or unknown objects directly.
    if value.__class__.__name__ in {"DataFrame", "Series"}:
        return f"<{value.__class__.__name__}: omitted from GPT payload>"

    return value


def build_report_payload(
    engine_output: Dict[str, Any],
    subject_profile: Optional[Dict[str, Any]] = None,
    market_inspection: Optional[Dict[str, Any]] = None,
    user_notes: str = "",
    estimated_days_until_market: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create the structured package that gets passed to mini GPT.

    The payload tells GPT what the program did and what was affected, so GPT
    can explain the outcome without inventing valuation logic.
    """
    engine_output = engine_output or {}
    subject_profile = subject_profile or engine_output.get("subject_summary", {}) or {}
    market_inspection = market_inspection or {}

    rows_loaded = engine_output.get("rows_loaded")
    closed_rows = engine_output.get("closed_rows")
    closed_band_rows = engine_output.get("closed_rows_in_subject_size_band")

    payload: Dict[str, Any] = {
        "payload_name": "ichiban_analysis_payload",
        "payload_version": "1.0",
        "created_by": "ICHIBAN local Streamlit app",
        "mini_gpt_role": {
            "primary_instruction": "Write the final ICHIBAN Insight report from the completed structured analysis package.",
            "do_not_recalculate_value": True,
            "do_not_change_deterministic_math": True,
            "narrative_task": "Explain what the program did, what affected value, what the local market means for this specific property, and how the agent should discuss going to market.",
        },
        "workflow_audit": {
            "subject_profile_ready": bool(subject_profile.get("subject_profile_ready")),
            "market_file_loaded": rows_loaded is not None,
            "rows_loaded": rows_loaded,
            "detected_header_row": engine_output.get("detected_header_row"),
            "header_score": engine_output.get("header_score"),
            "closed_rows_identified": closed_rows,
            "closed_rows_in_subject_size_band": closed_band_rows,
            "subject_size_filter_rule": "Closed comps filtered by 85% to 110% of subject above-grade square footage when above-grade square footage is available.",
            "governance_file_expected": "core/governance/ICHIBAN_Insight_Report_Governance_v2.json",
            "report_depth_mode": "deep_dive_no_page_cap",
            "output_preference": ".docx_first_clean_export",
        },
        "subject_property": {
            "subject_address": subject_profile.get("subject_address"),
            "above_grade_sqft": subject_profile.get("above_grade_sqft"),
            "basement_sqft": subject_profile.get("basement_sqft"),
            "finished_basement_sqft": subject_profile.get("finished_basement_sqft"),
            "property_type": subject_profile.get("property_type"),
            "property_subtype": subject_profile.get("property_subtype"),
            "beds": subject_profile.get("beds"),
            "baths": subject_profile.get("baths"),
            "year_built": subject_profile.get("year_built"),
            "garage_spaces": subject_profile.get("garage_spaces"),
            "real_avm": subject_profile.get("real_avm"),
            "real_avm_low": subject_profile.get("real_avm_low"),
            "real_avm_high": subject_profile.get("real_avm_high"),
            "zillow_estimate": subject_profile.get("zillow_estimate"),
            "redfin_estimate": subject_profile.get("redfin_estimate"),
            "agent_notes": user_notes,
        },
        "market_data_handoff": {
            "matched_market_fields": engine_output.get("matched_market_fields", {}),
            "missing_preferred_market_fields": engine_output.get("missing_preferred_market_fields", []),
            "normalized_columns": engine_output.get("normalized_columns", []),
            "market_inspection_summary": market_inspection,
        },
        "valuation_engine_output": engine_output,
        "report_inclusion_controls": {
            "estimated_days_until_market": estimated_days_until_market,
            "include_detailed_comp_tables_rule": "Include detailed comp tables only when estimated_days_until_market <= 30. Otherwise summarize and recommend refresh within 30 days of listing.",
        },
        "required_gpt_behavior": {
            "use_fixed_report_sections": True,
            "write_deep_dive_analysis": True,
            "avoid_generic_market_language": True,
            "explain_subject_specific_timeline": True,
            "explain_faster_or_slower_than_micro_market": True,
            "explain_what_moves_value_up_or_down": True,
            "include_required_disclaimer_section": True,
            "use_agent_advisor_voice": True,
            "do_not_present_as_appraisal": True,
        },
    }

    return _json_safe(payload)
