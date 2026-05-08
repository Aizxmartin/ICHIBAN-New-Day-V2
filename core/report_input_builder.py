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


def build_ruler_range(
    pricing_reconciliation: Dict[str, Any],
    selected_comparable_evidence_range: Dict[str, Any],
    online_estimated_value: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the standardized Ruler Range object.

    This is intentionally a data object, not a graphic. GPT/report export can
    render it as text, markdown, a visual bar, or later a DOCX element.
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
        )
    )

    ruler_low = first_available(final_low, comp_low, online_average)
    ruler_high = first_available(final_high, comp_high, online_average)

    markers = []
    if online_average is not None:
        markers.append({"label": "Online Estimate Average", "value": online_average})
    if comp_low is not None:
        markers.append({"label": "Selected Comp Evidence — Low", "value": comp_low})
    if comp_high is not None:
        markers.append({"label": "Selected Comp Evidence — High", "value": comp_high})
    if final_low is not None:
        markers.append({"label": "Recommended Range — Low", "value": final_low})
    if final_high is not None:
        markers.append({"label": "Recommended Range — High", "value": final_high})
    if recommended is not None:
        markers.append({"label": "Recommended List Posture", "value": recommended})

    return compact_dict(
        {
            "include_in_all_reports": True,
            "purpose": "Standardized seller-facing visual anchor for pricing discussion.",
            "ruler_low": ruler_low,
            "ruler_high": ruler_high,
            "recommended_price_range_low": final_low,
            "recommended_price_range_high": final_high,
            "recommended_list_price": recommended,
            "markers": markers,
            "angle_comment_prompt": (
                "Explain what supports the low end, what supports the high end, "
                "and whether the seller is choosing a protective, market-aligned, "
                "or more aggressive pricing posture."
            ),
        }
    )


def build_pricing_reconciliation(
    manual_pricing: Optional[Dict[str, Any]],
    engine_output: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the final pricing-reconciliation object.

    The current v2b engine intentionally does not force the final Market Entry
    Range. This object lets the agent/GPT handoff carry a narrow recommended range
    when the Realtor supplies it or when a later engine version creates it.
    """
    manual_pricing = manual_pricing or {}
    engine_reconciliation = engine_output.get("pricing_reconciliation") or {}

    selected_range = engine_output.get("selected_comparable_evidence_range") or {}

    low = first_available(
        manual_pricing.get("recommended_price_range_low"),
        engine_reconciliation.get("recommended_price_range_low"),
        engine_reconciliation.get("range_low"),
    )
    high = first_available(
        manual_pricing.get("recommended_price_range_high"),
        engine_reconciliation.get("recommended_price_range_high"),
        engine_reconciliation.get("range_high"),
    )
    recommended = first_available(
        manual_pricing.get("recommended_list_price"),
        engine_reconciliation.get("recommended_list_price"),
    )

    range_width = None
    low_num = money_or_none(low)
    high_num = money_or_none(high)
    if low_num is not None and high_num is not None:
        range_width = abs(high_num - low_num)

    return compact_dict(
        {
            "recommended_price_range_low": low_num,
            "recommended_price_range_high": high_num,
            "recommended_list_price": money_or_none(recommended),
            "range_width": range_width,
            "pricing_strategy_posture": first_available(
                manual_pricing.get("pricing_strategy_posture"),
                engine_reconciliation.get("pricing_strategy_posture"),
            ),
            "seller_goal": manual_pricing.get("seller_goal"),
            "estimated_days_until_market": manual_pricing.get("estimated_days_until_market"),
            "realtor_pricing_notes": manual_pricing.get("realtor_pricing_notes"),
            "engine_selected_comparable_evidence_range": selected_range,
            "range_policy_note": (
                "ICHIBAN should always produce a recommended range. The preferred seller-facing range is usually $50,000 or less unless "
                "limited data, unusual property traits, condition uncertainty, market volatility, or as-is vs improved scenarios justify a wider range."
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
    pricing_reconciliation = build_pricing_reconciliation(manual_pricing, engine_output)
    ruler_range = build_ruler_range(
        pricing_reconciliation=pricing_reconciliation,
        selected_comparable_evidence_range=selected_comparable_evidence_range,
        online_estimated_value=online_estimated_value,
    )

    report_input = {
        "report_input_version": "gpt_report_handoff_v1",
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
            "baseline_style": "Boca-style concise seller-friendly report with Ruler Range.",
            "include_ruler_range": True,
            "include_market_momentum_near_recommended_range": True,
            "main_comp_table_policy": "Keep main comp table tight: address, closed/net price, close date, Days in MLS, total adjusted price/range result.",
            "adjustment_detail_policy": "Use generalized Adjustment Summary instead of cluttering seller report with line-by-line comp adjustments.",
            "buyer_considerations_label": "Buyer Considerations",
            "avoid_confidence_score": True,
            "avoid_backend_language": True,
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
