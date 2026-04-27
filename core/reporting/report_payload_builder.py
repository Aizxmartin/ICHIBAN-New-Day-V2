"""
Builds the structured ICHIBAN payload sent to the GPT report writer.

Important design rule:
- Python/local app owns deterministic math and field organization.
- Mini GPT owns narrative explanation only.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Iterable, Optional


def _json_safe(value: Any) -> Any:
    """Convert common non-JSON values into plain Python-safe values."""
    if value is None:
        return None

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

    if value.__class__.__name__ in {"DataFrame", "Series"}:
        return f"<{value.__class__.__name__}: omitted from GPT payload>"

    return value


def _row_count(value: Any) -> Optional[int]:
    if value is None:
        return None
    if value.__class__.__name__ in {"DataFrame", "Series"}:
        return int(len(value))
    if isinstance(value, (list, tuple, set, dict)):
        return int(len(value))
    try:
        return int(value)
    except Exception:
        return None


def _money(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _records_from_dataframe(value: Any, limit: int = 12, columns: Optional[Iterable[str]] = None) -> list[dict[str, Any]]:
    if value is None or value.__class__.__name__ != "DataFrame":
        return []

    df = value.copy()
    if columns:
        keep = [c for c in columns if c in df.columns]
        if keep:
            df = df[keep]

    # Keep the payload focused. Mini GPT needs evidence, not the full MLS export.
    df = df.head(limit)
    records = df.to_dict(orient="records")
    return _json_safe(records)


def _compact_debug(debug: Dict[str, Any]) -> Dict[str, Any]:
    debug = debug or {}
    keep_keys = [
        "input_rows",
        "status_column_used",
        "net_close_price_column_used",
        "close_price_column_used",
        "above_grade_sqft_column_used",
        "status_value_counts",
        "subject_above_grade_sqft",
        "ag_band_low",
        "ag_band_high",
        "outlier_low",
        "outlier_high",
        "post_outlier_count",
        "outlier_note",
        "reason",
        "reason_no_ag_filter",
    ]
    return {key: _json_safe(debug.get(key)) for key in keep_keys if key in debug}


def _build_engine_summary(engine_output: Dict[str, Any]) -> Dict[str, Any]:
    debug = engine_output.get("debug", {}) or {}
    return {
        "rows_loaded": debug.get("input_rows") or engine_output.get("rows_loaded"),
        "closed_rows_identified": _row_count(engine_output.get("closed_rows")),
        "priced_closed_rows": _row_count(engine_output.get("priced_closed_rows")),
        "candidate_comps": _row_count(engine_output.get("candidate_comps")),
        "selected_comps": _row_count(engine_output.get("selected_comps")),
        "recommended_low": _money(engine_output.get("recommended_low")),
        "recommended_high": _money(engine_output.get("recommended_high")),
        "average_ppsf": _money(engine_output.get("average_ppsf")),
        "median_effective_price": _money(engine_output.get("median_effective_price")),
        "status_value_counts": _json_safe(debug.get("status_value_counts", {})),
        "subject_size_band_low": _money(debug.get("ag_band_low")),
        "subject_size_band_high": _money(debug.get("ag_band_high")),
        "comp_filter_rule_applied": "Closed comps filtered by 85% to 110% of subject above-grade square footage when available.",
        "outlier_filter": {
            "low": _money(debug.get("outlier_low")),
            "high": _money(debug.get("outlier_high")),
            "post_outlier_count": debug.get("post_outlier_count"),
            "note": debug.get("outlier_note"),
        },
    }


def _build_avm_summary(subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Keep AVM evidence separate from comp-based value evidence."""
    entries: list[dict[str, Any]] = []

    def add_entry(label: str, value: Any = None, low: Any = None, high: Any = None) -> None:
        value_num = _money(value)
        low_num = _money(low)
        high_num = _money(high)
        if value_num is None and low_num is None and high_num is None:
            return
        entries.append(
            {
                "source": label,
                "estimate": value_num,
                "range_low": low_num,
                "range_high": high_num,
            }
        )

    add_entry(
        "RealAVM",
        subject_profile.get("real_avm"),
        subject_profile.get("real_avm_low") or subject_profile.get("real_avm_range_low"),
        subject_profile.get("real_avm_high") or subject_profile.get("real_avm_range_high"),
    )
    add_entry("Zillow", subject_profile.get("zillow_estimate") or subject_profile.get("zestimate"))
    add_entry("Redfin", subject_profile.get("redfin_estimate"))

    range_values: list[float] = []
    for item in entries:
        for key in ("range_low", "range_high", "estimate"):
            if item.get(key) is not None:
                range_values.append(float(item[key]))

    return {
        "supplied": bool(entries),
        "source_priority": "secondary_reference_only",
        "rule": "AVM evidence may support or conflict with comp evidence, but it must not be mixed into the primary comp-based range.",
        "entries": entries,
        "avm_range_low": min(range_values) if range_values else None,
        "avm_range_high": max(range_values) if range_values else None,
    }


def _build_1004mc_handoff(one_hundred_four_mc_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = one_hundred_four_mc_summary or {}
    if not summary:
        return {
            "is_supplied": False,
            "source_status": "not_supplied",
            "annual_market_change_percent": None,
            "monthly_market_change_percent": None,
            "market_trend_classification": "not_supplied",
            "time_adjustments_supported": False,
            "rule": "1004MC is optional. If not supplied, valuation proceeds without formal time-trend adjustment evidence.",
        }

    return {
        "is_supplied": bool(summary.get("is_supplied")),
        "source_status": summary.get("source_status"),
        "annual_market_change_percent": _money(summary.get("annual_market_change_percent")),
        "monthly_market_change_percent": _money(summary.get("monthly_market_change_percent")),
        "market_trend_classification": summary.get("market_trend_classification"),
        "time_adjustments_supported": bool(summary.get("time_adjustments_supported")),
        "manual_note": summary.get("manual_note"),
        "parser_summary": summary.get("parser_summary", {}),
        "file_metadata": summary.get("file_metadata", {}),
        "rule": "1004MC/time-trend evidence is considered before comp time adjustments. GPT may explain supplied trend evidence but must not invent time adjustments not calculated by the local engine.",
    }


def build_report_payload(
    engine_output: Dict[str, Any],
    subject_profile: Optional[Dict[str, Any]] = None,
    market_inspection: Optional[Dict[str, Any]] = None,
    user_notes: str = "",
    estimated_days_until_market: Optional[int] = None,
    one_hundred_four_mc_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create the structured package passed to mini GPT.

    The payload tells GPT what the program did and what was affected, so GPT
    can explain the outcome without inventing valuation logic.
    """
    engine_output = engine_output or {}
    subject_profile = subject_profile or engine_output.get("subject_summary", {}) or {}
    market_inspection = market_inspection or {}
    debug = engine_output.get("debug", {}) or {}
    engine_summary = _build_engine_summary(engine_output)

    selected_comp_columns = [
        "street_number",
        "street_name",
        "mls_status",
        "above_grade_sqft",
        "beds",
        "baths",
        "year_built",
        "days_in_mls",
        "net_close_price",
        "close_price",
        "effective_sale_price",
        "effective_ppsf",
        "levels",
        "garage_spaces",
        "subdivision_name",
    ]

    selected_comp_source = engine_output.get("selected_comp_preview")
    if selected_comp_source is None:
        selected_comp_source = engine_output.get("selected_comps")

    selected_comp_preview = _records_from_dataframe(
        selected_comp_source,
        limit=12,
        columns=selected_comp_columns,
    )

    avm_summary = _build_avm_summary(subject_profile)
    mc_handoff = _build_1004mc_handoff(
        one_hundred_four_mc_summary or engine_output.get("one_hundred_four_mc_summary")
    )

    payload: Dict[str, Any] = {
        "payload_name": "ichiban_analysis_payload",
        "payload_version": "2.1_pre_api_handoff_cleanup",
        "created_by": "ICHIBAN local Streamlit app",
        "mini_gpt_role": {
            "primary_instruction": "Write the final ICHIBAN Insight report from the completed structured analysis package.",
            "do_not_recalculate_value": True,
            "do_not_change_deterministic_math": True,
            "narrative_task": "Explain what the program did, what affected value, what the local market means for this specific property, and how the agent should discuss going to market.",
        },
        "workflow_audit": {
            "subject_profile_ready": bool(subject_profile.get("subject_profile_ready")),
            "market_file_loaded": bool(engine_summary.get("rows_loaded")),
            "rows_loaded": engine_summary.get("rows_loaded"),
            "detected_header_row": market_inspection.get("detected_header_row"),
            "header_score": market_inspection.get("header_score"),
            "closed_rows_identified": engine_summary.get("closed_rows_identified"),
            "priced_closed_rows": engine_summary.get("priced_closed_rows"),
            "candidate_comps": engine_summary.get("candidate_comps"),
            "selected_comps": engine_summary.get("selected_comps"),
            "subject_size_filter_rule": engine_summary.get("comp_filter_rule_applied"),
            "governance_file_expected": "core/governance/ICHIBAN_Insight_Report_Governance_v2.json",
            "report_depth_mode": "deep_dive_no_page_cap",
            "output_preference": ".docx_first_clean_export",
            "client_report_rule": "Do not expose internal implementation notes or formula category labels in the client report. Translate limitations into market-facing language.",
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
            "agent_notes": user_notes,
        },
        "valuation_ranges": {
            "presentation_order": [
                "avm_based_range_if_supplied",
                "comp_based_range",
                "recommended_list_price_range_when_available",
            ],
            "avm_based_range_if_supplied": avm_summary,
            "comp_based_range": {
                "source_priority": "primary_valuation_evidence",
                "range_type": "selected_comparable_sale_evidence",
                "low": engine_summary.get("recommended_low"),
                "high": engine_summary.get("recommended_high"),
                "median_effective_sale_price": engine_summary.get("median_effective_price"),
                "average_ppsf": engine_summary.get("average_ppsf"),
                "rule": "This is comp-based evidence. It must not be blended with AVM estimates.",
            },
            "recommended_list_price_range": {
                "source_priority": "final_strategy_output",
                "low": _money(engine_output.get("suggested_list_low") or engine_output.get("final_recommended_low")),
                "high": _money(engine_output.get("suggested_list_high") or engine_output.get("final_recommended_high")),
                "status": "not_calculated_yet" if not (engine_output.get("suggested_list_low") or engine_output.get("final_recommended_low")) else "supplied_by_engine",
                "rule": "Recommended list range should derive from comp-based evidence and agent strategy; AVMs may be discussed as secondary support only.",
            },
        },
        "one_hundred_four_mc_handoff": mc_handoff,
        "market_data_handoff": {
            "matched_market_fields": market_inspection.get("matched_fields", {}),
            "missing_preferred_market_fields": market_inspection.get("missing_preferred_fields", []),
            "normalized_columns": market_inspection.get("normalized_columns", []),
            "status_value_counts": engine_summary.get("status_value_counts"),
        },
        "valuation_engine_summary": engine_summary,
        "selected_comparable_preview": selected_comp_preview,
        "debug_summary_for_developer_review": _compact_debug(debug),
        "internal_processing_notes_for_model_not_client_language": {
            "purpose": "These notes help Mini GPT reason correctly but should not be copied into the polished client report.",
            "technical_limitations": [
                "If full physical adjustment math is not present, discuss comp spread and property-specific uncertainty in client-safe language rather than naming missing modules.",
                "If 1004MC/time-adjusted prices are not present, explain that the analysis relies on available closed-sale evidence and should be refreshed near listing.",
                "Do not use words like payload, module, deterministic engine, API, or debug in the client-facing report body.",
            ],
        },
        "report_inclusion_controls": {
            "estimated_days_until_market": estimated_days_until_market,
            "include_detailed_comp_tables_rule": "Include detailed comp tables only when estimated_days_until_market <= 30. Otherwise summarize and recommend refresh within 30 days of listing.",
            "include_detailed_comp_tables": bool(estimated_days_until_market is not None and estimated_days_until_market <= 30),
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
            "separate_avm_range_from_comp_range": True,
            "do_not_mix_avms_into_comp_based_range": True,
            "hide_technical_backend_language_from_client_report": True,
            "use_boilerplate_disclaimer_without_formula_discussion": True,
        },
    }

    return _json_safe(payload)
