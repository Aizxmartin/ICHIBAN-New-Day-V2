from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_VALUATION_ENGINE_OUTPUT_PATH = DATA_DIR / "valuation_engine_output.json"
DEFAULT_VALUATION_INPUT_PACKAGE_PATH = DATA_DIR / "valuation_input_package.json"
DEFAULT_REPORT_INPUT_PATH = DATA_DIR / "report_input.json"
CURRENT_REPORT_INPUT_VERSION = "gpt_report_handoff_v4_blueprint_enforced"


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------


def json_safe(value: Any) -> Any:
    """Convert common Python objects into JSON-safe structures."""
    if value is None:
        return None

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "to_dict") and hasattr(value, "columns"):
        try:
            return value.to_dict(orient="records")
        except Exception:
            return str(value)

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]

    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def load_json_file(path: str | Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a JSON object from disk. Return default when missing/invalid."""
    default = default or {}
    path = Path(path)

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            return data
    except Exception:
        return default

    return default


def save_json_file(path: str | Path, data: Dict[str, Any]) -> Path:
    """Save a JSON object and return the saved path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(json_safe(data), file, indent=2, ensure_ascii=False)

    return path


def to_number(value: Any) -> Optional[float]:
    """Convert currency/number text to float when possible."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", ".", "-", "-."}:
        return None

    try:
        return float(cleaned)
    except Exception:
        return None


def money_or_none(value: Any) -> Optional[int]:
    """Return a rounded integer dollar value when possible."""
    number = to_number(value)
    if number is None:
        return None
    return int(round(number))


def compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove empty/null fields at the top level for a cleaner GPT payload."""
    compacted: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if value == "":
            continue
        if value == []:
            continue
        if value == {}:
            continue
        compacted[key] = value
    return compacted


def combine_notes(*groups: Any) -> List[str]:
    """Combine note/warning lists while preserving order and removing duplicates."""
    output: List[str] = []
    seen = set()

    for group in groups:
        if group is None:
            continue
        if isinstance(group, str):
            items = [group]
        elif isinstance(group, list):
            items = group
        else:
            items = [str(group)]

        for item in items:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key not in seen:
                output.append(text)
                seen.add(key)

    return output


# ---------------------------------------------------------------------
# Valuation-engine unwrapping
# ---------------------------------------------------------------------


def unwrap_engine_output(valuation_engine_result: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Module 4 currently saves a wrapper object:
    {
      "engine_status": "success",
      "engine_module": "core.valuation_engine",
      "engine_function": "run_valuation_engine",
      "engine_output": {...actual valuation output...}
    }

    This helper returns (engine_output, wrapper_metadata).
    """
    if not valuation_engine_result:
        return {}, {}

    if isinstance(valuation_engine_result.get("engine_output"), dict):
        wrapper_metadata = {
            "module_4_wrapper_status": valuation_engine_result.get("engine_status"),
            "engine_module": valuation_engine_result.get("engine_module"),
            "engine_function": valuation_engine_result.get("engine_function"),
        }
        return valuation_engine_result.get("engine_output") or {}, compact_dict(wrapper_metadata)

    return valuation_engine_result, {}


def first_available(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value is None:
            continue
        if value == "":
            continue
        if value == []:
            continue
        if value == {}:
            continue
        return value
    return None


# ---------------------------------------------------------------------
# Report input assembly
# ---------------------------------------------------------------------



def round_to_nearest_5000(value: Any) -> Optional[int]:
    """Round a dollar value to the nearest $5,000 for seller-facing price guidance."""
    number = money_or_none(value)
    if number is None:
        return None
    return int(round(number / 5000) * 5000)


def derive_fallback_recommended_range(engine_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a conservative draft Market Entry Range when the Realtor has not entered one.

    This is intentionally narrower than the selected-comp evidence band. It uses the
    center of the selected comparable evidence (median and weighted average) as a
    starting point and leaves room for Realtor/GPT qualification based on condition,
    active competition, momentum, and showing preparation.
    """
    comp_stats = engine_output.get("comp_statistics") or {}
    selected_range = engine_output.get("selected_comparable_evidence_range") or {}

    median_adjusted = money_or_none(
        first_available(
            comp_stats.get("median_adjusted_price"),
            comp_stats.get("median_adjusted_value"),
            comp_stats.get("median_net_price"),
        )
    )
    weighted_adjusted = money_or_none(
        first_available(
            comp_stats.get("weighted_adjusted_average"),
            comp_stats.get("average_adjusted_price"),
            comp_stats.get("median_adjusted_price"),
        )
    )

    evidence_low = money_or_none(selected_range.get("range_low"))
    evidence_high = money_or_none(selected_range.get("range_high"))

    if median_adjusted is None and weighted_adjusted is None:
        return {}

    center_low = min(v for v in [median_adjusted, weighted_adjusted] if v is not None)
    center_high = max(v for v in [median_adjusted, weighted_adjusted] if v is not None)

    # Preferred ICHIBAN behavior: do not let the seller-facing recommendation
    # become the full comp spread. Start with a narrow practical lane.
    draft_low = round_to_nearest_5000(center_low - 5000)
    draft_high = round_to_nearest_5000(center_high + 5000)

    if draft_low is None or draft_high is None:
        return {}

    if draft_high <= draft_low:
        draft_high = draft_low + 15000

    # Keep the default range disciplined. Wider ranges require explicit Realtor
    # input, unusual property facts, or limited-data caveats.
    if draft_high - draft_low > 50000:
        draft_high = draft_low + 50000

    # Do not propose a draft range outside the selected evidence band when that
    # band exists. This is only a seller-facing starting lane.
    if evidence_low is not None:
        draft_low = max(draft_low, round_to_nearest_5000(evidence_low) or draft_low)
    if evidence_high is not None:
        draft_high = min(draft_high, round_to_nearest_5000(evidence_high) or draft_high)

    draft_recommended = round_to_nearest_5000(median_adjusted or weighted_adjusted or center_low)
    if draft_recommended is not None:
        draft_recommended = max(draft_low, min(draft_recommended, draft_high))

    return compact_dict(
        {
            "recommended_price_range_low": draft_low,
            "recommended_price_range_high": draft_high,
            "recommended_list_price": draft_recommended,
            "range_width": draft_high - draft_low,
            "pricing_strategy_posture": "Evidence-Aligned / Recommended",
            "source": "auto_draft_from_comp_center_locked_range",
            "requires_realtor_review": True,
            "derivation_note": (
                "Draft range derived from selected comparable median/weighted adjusted evidence. "
                "It should be tightened or shifted by Realtor notes, current competition, condition, and launch strategy."
            ),
        }
    )


def build_ruler_range(
    pricing_reconciliation: Dict[str, Any],
    selected_comparable_evidence_range: Dict[str, Any],
    online_estimated_value: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the standardized Ruler Range object used by both GPT and DOCX export.

    The Ruler Range is broader evidence context. The Recommended Market Entry
    Range is the narrower lane the Realtor/Seller discusses for launch posture.
    """
    final_low = money_or_none(pricing_reconciliation.get("recommended_price_range_low"))
    final_high = money_or_none(pricing_reconciliation.get("recommended_price_range_high"))
    recommended = money_or_none(pricing_reconciliation.get("recommended_list_price"))

    comp_low = money_or_none(
        first_available(
            selected_comparable_evidence_range.get("range_low"),
            selected_comparable_evidence_range.get("low"),
            selected_comparable_evidence_range.get("selected_range_low"),
            selected_comparable_evidence_range.get("adjusted_low"),
        )
    )
    comp_high = money_or_none(
        first_available(
            selected_comparable_evidence_range.get("range_high"),
            selected_comparable_evidence_range.get("high"),
            selected_comparable_evidence_range.get("selected_range_high"),
            selected_comparable_evidence_range.get("adjusted_high"),
        )
    )

    online_average = money_or_none(
        first_available(
            online_estimated_value.get("online_estimate_average"),
            online_estimated_value.get("average"),
            online_estimated_value.get("average_online_estimate"),
            online_estimated_value.get("range_low"),
        )
    )

    ruler_low = first_available(comp_low, final_low, online_average)
    ruler_high = first_available(comp_high, final_high, online_average)

    markers = []
    if comp_low is not None:
        markers.append({"label": "Market Support", "value": comp_low, "meaning": "Lower selected-comp support"})
    if final_low is not None:
        markers.append({"label": "Lower Entry", "value": final_low, "meaning": "Practical entry lane begins"})
    if recommended is not None:
        markers.append({"label": "Target Position", "value": recommended, "meaning": "Best evidence-aligned launch posture"})
    if final_high is not None:
        markers.append({"label": "Strategic Upper", "value": final_high, "meaning": "Upper practical entry lane; requires strong presentation"})
    if comp_high is not None:
        markers.append({"label": "High-Risk Stretch", "value": comp_high, "meaning": "Upper evidence marker; not an automatic list price"})
    if online_average is not None:
        markers.append({"label": "Online Benchmark", "value": online_average, "meaning": "AVM/online context only"})

    range_indicator_comments = [
        {
            "label": "Market Support",
            "comment": (
                "Lower evidence-supported area. May improve buyer traffic, especially if speed is important, "
                "but should be weighed against presentation and current competition."
            ),
        },
        {
            "label": "Target Position",
            "comment": (
                "Best evidence-aligned launch lane based on closed comparable sales, online benchmarks, "
                "condition, current competition, and market momentum."
            ),
        },
        {
            "label": "Strategic Upper",
            "comment": (
                "Potentially defensible when presentation is strong, inventory is favorable, and buyers clearly respond "
                "to the property’s layout and features."
            ),
        },
        {
            "label": "High-Risk Stretch",
            "comment": (
                "Requires stronger support such as superior updates, unusually low competition, or exceptional early feedback. "
                "Without that support, this range carries higher risk of longer Days in MLS and future price reduction."
            ),
        },
    ]

    return compact_dict(
        {
            "include_in_all_reports": True,
            "purpose": "Standardized seller-facing visual anchor for pricing discussion.",
            "standard_labels": ["Market Support", "Lower Entry", "Target Position", "Strategic Upper", "High-Risk Stretch"],
            "ruler_low": ruler_low,
            "ruler_high": ruler_high,
            "recommended_price_range_low": final_low,
            "recommended_price_range_high": final_high,
            "recommended_list_price": recommended,
            "markers": markers,
            "range_indicator_comments": range_indicator_comments,
            "ruler_policy_note": (
                "Ruler Range shows evidence context. Recommended Range is the narrower launch-pricing lane. "
                "The high-end evidence marker is a High-Risk Stretch unless updates, low inventory, or buyer response support it."
            ),
        }
    )


def build_pricing_reconciliation(
    manual_pricing: Optional[Dict[str, Any]],
    engine_output: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the final pricing object.

    User/Realtor entries win. If they are absent, use a conservative auto-draft
    from comp center evidence so GPT does not invent a broad or aggressive range.
    """
    manual_pricing = manual_pricing or {}
    engine_reconciliation = engine_output.get("pricing_reconciliation") or {}
    selected_range = engine_output.get("selected_comparable_evidence_range") or {}

    manual_or_engine_low = first_available(
        manual_pricing.get("recommended_price_range_low"),
        engine_reconciliation.get("recommended_price_range_low"),
        engine_reconciliation.get("range_low"),
    )
    manual_or_engine_high = first_available(
        manual_pricing.get("recommended_price_range_high"),
        engine_reconciliation.get("recommended_price_range_high"),
        engine_reconciliation.get("range_high"),
    )
    manual_or_engine_recommended = first_available(
        manual_pricing.get("recommended_list_price"),
        engine_reconciliation.get("recommended_list_price"),
    )

    manual_price_override = bool(manual_pricing.get("manual_price_override"))
    manual_has_range = manual_price_override and any(
        money_or_none(manual_pricing.get(key)) is not None
        for key in [
            "recommended_price_range_low",
            "recommended_price_range_high",
            "recommended_list_price",
        ]
    )
    source = "manual_user_entry" if manual_has_range else "manual_or_engine"

    if manual_price_override:
        low_num = money_or_none(manual_or_engine_low)
        high_num = money_or_none(manual_or_engine_high)
        recommended_num = money_or_none(manual_or_engine_recommended)
    else:
        # Form defaults should not become a manual range just because the user clicked Build/Refresh.
        # Without an explicit override, always re-derive the current evidence-based draft range.
        low_num = None
        high_num = None
        recommended_num = None

    fallback = {}
    if low_num is None or high_num is None:
        fallback = derive_fallback_recommended_range(engine_output)
        low_num = first_available(low_num, fallback.get("recommended_price_range_low"))
        high_num = first_available(high_num, fallback.get("recommended_price_range_high"))
        recommended_num = first_available(recommended_num, fallback.get("recommended_list_price"))
        source = fallback.get("source", "auto_draft_from_comp_center") if fallback else source

    range_width = None
    if low_num is not None and high_num is not None:
        range_width = abs(int(high_num) - int(low_num))

    return compact_dict(
        {
            "recommended_price_range_low": low_num,
            "recommended_price_range_high": high_num,
            "recommended_list_price": recommended_num,
            "range_width": range_width,
            "pricing_strategy_posture": first_available(
                manual_pricing.get("pricing_strategy_posture"),
                engine_reconciliation.get("pricing_strategy_posture"),
                fallback.get("pricing_strategy_posture") if fallback else None,
            ),
            "seller_goal": manual_pricing.get("seller_goal"),
            "estimated_days_until_market": manual_pricing.get("estimated_days_until_market"),
            "realtor_pricing_notes": manual_pricing.get("realtor_pricing_notes"),
            "source": source,
            "manual_price_override": manual_price_override,
            "requires_realtor_review": bool(fallback.get("requires_realtor_review")) if fallback else False,
            "draft_range_derivation_note": fallback.get("derivation_note") if fallback else None,
            "engine_selected_comparable_evidence_range": selected_range,
            "range_policy_note": (
                "ICHIBAN should always separate the broad selected-comp evidence range from the narrower seller-facing Recommended Market Entry Range. "
                "The preferred seller-facing range is usually $50,000 or less unless limited data, unusual property traits, condition uncertainty, "
                "market volatility, or as-is vs improved scenarios justify a wider range."
            ),
        }
    )


def build_current_competition_check(market_momentum: Dict[str, Any]) -> Dict[str, Any]:
    """Create a distinct competition object so reports keep competition separate from momentum."""
    market_momentum = market_momentum or {}
    return compact_dict(
        {
            "section_label": "Current Competition Check",
            "active_count": market_momentum.get("active_count"),
            "coming_soon_count": market_momentum.get("coming_soon_count"),
            "pending_count": market_momentum.get("pending_count"),
            "closed_count": market_momentum.get("closed_count"),
            "average_dim_active": market_momentum.get("average_dim_active"),
            "average_dim_pending": market_momentum.get("average_dim_pending"),
            "source": market_momentum.get("source"),
            "status": market_momentum.get("status"),
            "important_limitation": market_momentum.get("important_limitation"),
            "reporting_rule": (
                "Active, Coming Soon, and Pending listings influence launch posture, buyer alternatives, and pricing risk. "
                "They do not create the closed-comp value range."
            ),
        }
    )

def build_report_input(
    valuation_engine_result: Optional[Dict[str, Any]] = None,
    valuation_input_package: Optional[Dict[str, Any]] = None,
    manual_pricing: Optional[Dict[str, Any]] = None,
    realtor_notes: Optional[str] = None,
    buyer_consideration_notes: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the structured JSON package that GPT receives after deterministic math.

    This is the bridge between Module 4 valuation math and the final GPT report.
    """
    valuation_engine_result = valuation_engine_result or load_json_file(DEFAULT_VALUATION_ENGINE_OUTPUT_PATH)
    valuation_input_package = valuation_input_package or load_json_file(DEFAULT_VALUATION_INPUT_PACKAGE_PATH)

    engine_output, wrapper_metadata = unwrap_engine_output(valuation_engine_result)
    manual_pricing = manual_pricing or {}
    additional_context = additional_context or {}

    subject_profile = first_available(
        engine_output.get("subject_summary"),
        valuation_input_package.get("subject_profile"),
        valuation_input_package.get("subject"),
        {},
    )

    selected_comparable_evidence_range = engine_output.get("selected_comparable_evidence_range") or {}
    online_estimated_value = engine_output.get("online_estimated_value") or {}
    market_momentum = engine_output.get("market_momentum_and_buyer_competition") or {}
    market_conditions_1004mc = first_available(
        engine_output.get("market_conditions_1004mc"),
        valuation_input_package.get("one_hundred_four_mc_summary"),
        {},
    )
    current_competition_check = build_current_competition_check(market_momentum)
    pricing_reconciliation = build_pricing_reconciliation(manual_pricing, engine_output)
    ruler_range = build_ruler_range(
        pricing_reconciliation=pricing_reconciliation,
        selected_comparable_evidence_range=selected_comparable_evidence_range,
        online_estimated_value=online_estimated_value,
    )

    report_input = {
        "report_input_version": CURRENT_REPORT_INPUT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "purpose": "Structured GPT handoff for ICHIBAN INSIGHT seller-facing report generation.",
        "workflow_boundary": {
            "math_first_gpt_second": True,
            "gpt_may_explain_but_not_recalculate": True,
            "private_logic_should_not_be_exposed_in_seller_report": True,
            "seller_facing_goal": "Clear, practical Realtor/Seller report with Ruler Range, pricing posture, market momentum, and Buyer Considerations.",
        },
        "source_metadata": compact_dict(
            {
                "module_4_wrapper": wrapper_metadata,
                "engine_version": engine_output.get("engine_version"),
                "engine_status": engine_output.get("engine_status"),
                "engine_scope": engine_output.get("engine_scope"),
                "market_rows_loaded": engine_output.get("market_rows_loaded") or valuation_input_package.get("market_rows"),
                "closed_rows_available": engine_output.get("closed_rows_available"),
                "comp_rows_scored": engine_output.get("comp_rows_scored"),
                "comp_rows_selected": engine_output.get("comp_rows_selected"),
            }
        ),
        "subject_property_summary": subject_profile,
        "online_estimates": online_estimated_value,
        "selected_comparable_evidence_range": selected_comparable_evidence_range,
        "selected_adjusted_comps": engine_output.get("selected_adjusted_comps") or [],
        "comp_statistics": engine_output.get("comp_statistics") or {},
        "current_competition_check": current_competition_check,
        "market_momentum": market_momentum,
        "market_conditions_1004mc": market_conditions_1004mc,
        "pricing_reconciliation": pricing_reconciliation,
        "ruler_range": ruler_range,
        "realtor_notes": realtor_notes or manual_pricing.get("realtor_notes") or "",
        "buyer_consideration_notes": buyer_consideration_notes or manual_pricing.get("buyer_consideration_notes") or "",
        "gpt_review_package": engine_output.get("gpt_review_package") or {},
        "data_verification_notes": combine_notes(
            engine_output.get("data_verification_notes"),
            valuation_input_package.get("data_verification_notes"),
            additional_context.get("data_verification_notes"),
        ),
        "warnings_and_limitations": combine_notes(
            engine_output.get("warnings"),
            valuation_engine_result.get("warnings") if isinstance(valuation_engine_result, dict) else None,
            valuation_input_package.get("warnings"),
            additional_context.get("warnings"),
        ),
        "notes": combine_notes(
            engine_output.get("notes"),
            valuation_input_package.get("notes"),
            additional_context.get("notes"),
        ),
        "report_output_preferences": {
            "baseline_style": "Boca-style concise seller-friendly report with visual Ruler Range and Range Indicator Comments.",
            "locked_section_order": [
                "Recommended Range + Ruler",
                "Executive Summary bullets",
                "Comparable Evidence table",
                "How the Value Was Determined / Generalized Adjustments",
                "AVM / Online Benchmarks",
                "Current Competition Check",
                "Market Momentum",
                "Buyer Considerations",
                "Strategy / Launch Notes",
                "Disclaimer",
            ],
            "include_ruler_range": True,
            "include_range_indicator_comments": True,
            "include_market_momentum_near_recommended_range": True,
            "separate_current_competition_from_momentum": True,
            "distance_from_subject_policy": "When distance-from-subject fields are available, include them in comp/competition review; do not invent distances.",
            "main_comp_table_policy": "Keep main comp table tight: address, distance if available, closed/net price, close date, Days in MLS, and total adjusted price/range result.",
            "adjustment_detail_policy": "Use How the Value Was Determined / Generalized Adjustments instead of cluttering seller report with line-by-line comp adjustments.",
            "buyer_considerations_label": "Buyer Considerations",
            "avoid_confidence_score": True,
            "avoid_backend_language": True,
            "avoid_gpt_language": True,
            "avoid_reconciliation_word": True,
        },
    }

    return json_safe(report_input)


def build_and_save_report_input(
    output_path: str | Path = DEFAULT_REPORT_INPUT_PATH,
    **kwargs: Any,
) -> Tuple[Dict[str, Any], Path]:
    """Build report_input.json, save it, and return both data and path."""
    report_input = build_report_input(**kwargs)
    path = save_json_file(output_path, report_input)
    return report_input, path
