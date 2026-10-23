from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.report_routing import DEFAULT_REPORT_VERSION, resolve_report_routing


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_VALUATION_ENGINE_OUTPUT_PATH = DATA_DIR / "valuation_engine_output.json"
DEFAULT_VALUATION_INPUT_PACKAGE_PATH = DATA_DIR / "valuation_input_package.json"
DEFAULT_REPORT_INPUT_PATH = DATA_DIR / "report_input.json"
CURRENT_REPORT_INPUT_VERSION = "gpt_report_handoff_v20_5_tarzan_valuation_analysis"


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
            "label": "Top of Range",
            "comment": (
                "Upper end of the selected range. This can be appropriate when presentation, condition, buyer confidence, "
                "and early market response support holding a firmer position."
            ),
        },
    ]

    return compact_dict(
        {
            "include_in_all_reports": True,
            "purpose": "Standardized seller-facing visual anchor for pricing discussion.",
            "standard_labels": ["Bottom of Range", "Recommended Position", "Top of Range"],
            "ruler_low": ruler_low,
            "ruler_high": ruler_high,
            "recommended_price_range_low": final_low,
            "recommended_price_range_high": final_high,
            "recommended_list_price": recommended,
            "markers": markers,
            "range_indicator_comments": range_indicator_comments,
            "ruler_policy_note": (
                "Ruler Range shows evidence context. Recommended Range is the narrower launch-pricing lane. "
                "The selected range should be shown once using the locked black-and-white Tarzan tick-mark ruler: Bottom of Range, Recommended Position, and Top of Range."
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



def _fmt_stack_money(value: Any) -> str:
    """Format dollars for Pricing Logic Stack text fields."""
    number = money_or_none(value)
    if number is None:
        return "—"
    if number == 0:
        return "$0"
    sign = "-" if number < 0 else ""
    return f"{sign}${abs(number):,.0f}"


def _pricing_midpoint(pricing_reconciliation: Dict[str, Any]) -> Optional[int]:
    low = money_or_none((pricing_reconciliation or {}).get("recommended_price_range_low"))
    high = money_or_none((pricing_reconciliation or {}).get("recommended_price_range_high"))
    target = money_or_none((pricing_reconciliation or {}).get("recommended_list_price"))
    if target is not None:
        return target
    if low is not None and high is not None:
        return int(round((low + high) / 2))
    return first_available(low, high)


def _safe_reason(text: Any, default: str) -> str:
    text = str(text or "").strip()
    return text if text else default


def _first_money_with_source(*candidates: tuple[str, Any]) -> tuple[Optional[int], str]:
    """Return first parseable money value and its source label."""
    for source, value in candidates:
        parsed = money_or_none(value)
        if parsed is not None:
            return parsed, source
    return None, "not supplied"


def _lower_text(value: Any) -> str:
    return str(value or "").lower()


def _contains_any(text: Any, keywords: List[str]) -> bool:
    t = _lower_text(text)
    return any(k.lower() in t for k in keywords)


def _comp_quality_flags(comp: Dict[str, Any], subject_profile: Dict[str, Any]) -> List[str]:
    """Deterministic red/yellow flags used before GPT writes narrative.

    This does not replace appraiser judgment. It makes sure the report writer sees
    issues that math-only scoring may miss: high DIM, concessions, superior/remodel
    claims, level mismatch, and large adjustment spread.
    """
    flags: List[str] = []
    score = to_number(comp.get("comp_score"))
    days = to_number(comp.get("days_in_mls"))
    concessions = money_or_none(comp.get("concessions")) or 0
    net_price = money_or_none(comp.get("net_price"))
    original_price = money_or_none(comp.get("original_list_price"))
    adjusted_price = money_or_none(comp.get("total_adjusted_price"))
    total_adjustments = money_or_none(comp.get("total_adjustments")) or 0
    subject_level = str(subject_profile.get("levels") or "").strip().lower()
    comp_level = str(comp.get("levels") or "").strip().lower()
    remarks = f"{comp.get('public_remarks_for_gpt_review') or ''} {comp.get('broker_remarks_for_gpt_review') or ''}"

    if score is not None and score < 75:
        flags.append("lower mathematical comp score")
    if comp.get("level_style_match") is False and subject_level:
        flags.append(f"level/style mismatch or unconfirmed: subject={subject_level or 'unknown'} comp={comp_level or 'unknown'}")
    if days is not None:
        if days >= 120:
            flags.append("extreme Days in MLS; do not let this comp control midpoint without explanation")
        elif days >= 60:
            flags.append("high Days in MLS; treat buyer acceptance carefully")
    if concessions and concessions >= 10000:
        flags.append("material seller concessions; review net-price support")
    if original_price is not None and net_price is not None and original_price > net_price:
        diff = original_price - net_price
        if diff >= 25000:
            flags.append("material net-below-original result; review seller-net behavior")
    if adjusted_price and abs(total_adjustments) / adjusted_price >= 0.08:
        flags.append("large adjustment load; comp should be qualified")
    if _contains_any(remarks, ["fully remodeled", "remodeled", "renovated", "designer", "quartz", "stunning", "spa-style", "new carpet", "fresh paint", "move-in-ready"]):
        flags.append("superior/remodeled presentation signals in remarks; review condition comparability")
    if _contains_any(remarks, ["back on the market", "inspection", "sat", "sitting", "needs the right buyer"]):
        flags.append("broker remarks show market acceptance or deal-friction signal")
    return flags


def _classify_comp_role(comp: Dict[str, Any], subject_profile: Dict[str, Any], comp_stats: Dict[str, Any]) -> str:
    flags = _comp_quality_flags(comp, subject_profile)
    score = to_number(comp.get("comp_score")) or 0
    adjusted_price = money_or_none(comp.get("total_adjusted_price"))
    weighted_center = money_or_none(comp_stats.get("weighted_adjusted_average"))
    median_adjusted = money_or_none(comp_stats.get("median_adjusted_price"))
    center = weighted_center or median_adjusted

    if any("level/style mismatch" in f for f in flags) or score < 60:
        return "Warning / Qualified Comp"
    if any("extreme Days" in f for f in flags) or any("large adjustment" in f for f in flags):
        return "Warning / Qualified Comp"
    if center and adjusted_price:
        if adjusted_price >= center + 25000:
            return "Upper Support"
        if adjusted_price <= center - 25000:
            return "Lower Support"
    if flags:
        return "Primary Comp — Qualified"
    return "Primary Comp"


def build_comparable_fit_audit(engine_output: Dict[str, Any], subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    comps = engine_output.get("selected_adjusted_comps") or []
    comp_stats = engine_output.get("comp_statistics") or {}
    rows: List[Dict[str, Any]] = []
    role_counts: Dict[str, int] = {}
    warnings: List[str] = []

    for comp in comps:
        if not isinstance(comp, dict):
            continue
        flags = _comp_quality_flags(comp, subject_profile)
        role = _classify_comp_role(comp, subject_profile, comp_stats)
        role_counts[role] = role_counts.get(role, 0) + 1
        if flags:
            warnings.append(f"{comp.get('address') or 'Unknown comp'}: " + "; ".join(flags))
        rows.append(compact_dict({
            "address": comp.get("address"),
            "role": role,
            "level": comp.get("levels"),
            "level_style_match": comp.get("level_style_match"),
            "comp_score": comp.get("comp_score"),
            "days_in_mls": comp.get("days_in_mls"),
            "net_price": comp.get("net_price"),
            "total_adjusted_price": comp.get("total_adjusted_price"),
            "concessions": comp.get("concessions"),
            "total_adjustments": comp.get("total_adjustments"),
            "audit_flags": flags,
        }))

    status = "PASS"
    if any(r.get("role") == "Warning / Qualified Comp" for r in rows):
        status = "QUALIFIED"
    if rows and role_counts.get("Primary Comp", 0) < 3:
        status = "HUMAN REVIEW REQUIRED"
        warnings.append("Fewer than three unqualified primary comps remain after Comparable Fit Audit.")

    return compact_dict({
        "section_title": "Comparable Fit Audit",
        "purpose": "Force a pre-report Tarzan review of whether selected comps are true comps, upper/lower support, or qualified evidence before final valuation narrative is written.",
        "subject_levels": subject_profile.get("levels"),
        "audit_status": status,
        "role_counts": role_counts,
        "selected_comp_count": len(rows),
        "comp_fit_rows": rows,
        "warnings": warnings,
        "rule": "A comp may support evidence without controlling the recommended midpoint. Superior, stale, high-DIM, high-concession, or unlike comps must be qualified in Tarzan and cannot be used as false support in Tarzan.",
    })


def build_cross_section_impact_review(
    pricing_reconciliation: Dict[str, Any],
    comp_fit_audit: Dict[str, Any],
    market_momentum: Dict[str, Any],
    price_sensitivity: Dict[str, Any],
    market_acceptance_repositioning_review: Dict[str, Any],
    after_active_pricing_review: Dict[str, Any],
) -> Dict[str, Any]:
    impacts: List[Dict[str, Any]] = []

    low = money_or_none(pricing_reconciliation.get("recommended_price_range_low"))
    high = money_or_none(pricing_reconciliation.get("recommended_price_range_high"))
    target = money_or_none(pricing_reconciliation.get("recommended_list_price"))
    current = money_or_none(after_active_pricing_review.get("current_list_price"))

    def add(section: str, effect: str, reason: str) -> None:
        impacts.append({"section": section, "effect_on_recommendation": effect, "reason": reason})

    if comp_fit_audit.get("audit_status") in {"QUALIFIED", "HUMAN REVIEW REQUIRED"}:
        add("Comparable Fit Audit", "QUALIFIES", "One or more selected comps require qualification before the range is presented as clean support.")
    else:
        add("Comparable Fit Audit", "CONFIRMS", "Selected comps do not show major deterministic fit warnings.")

    active_dim = to_number(market_momentum.get("average_dim_active"))
    pending_dim = to_number(market_momentum.get("average_dim_pending"))
    moi = to_number(market_momentum.get("primary_months_of_inventory"))
    if active_dim is not None and pending_dim is not None and active_dim > pending_dim * 1.75:
        add("Market Momentum", "WEAKENS", "Active listings are sitting materially longer than pending listings, which suggests buyers are selective and current competition matters.")
    elif moi is not None and moi <= 3:
        add("Market Momentum", "SUPPORTS", "Closed-only months of inventory is relatively limited, supporting a market-aligned position if the property competes well.")
    else:
        add("Market Momentum", "MIXED", "Momentum does not clearly confirm or reject the comp-supported range.")

    reduction_rate = to_number(price_sensitivity.get("closed_last_90_price_adjustment_behavior", {}).get("price_reduction_rate_percent"))
    concession_rate = to_number(price_sensitivity.get("seller_concession_rate_percent"))
    if (reduction_rate is not None and reduction_rate >= 30) or (concession_rate is not None and concession_rate >= 50):
        add("Price Sensitivity / Seller Net", "WEAKENS", "Recent closings show material reductions/concessions; pricing must be tested against buyer acceptance, not just comp math.")
    else:
        add("Price Sensitivity / Seller Net", "CONFIRMS", "Price-reduction/concession behavior does not create a major independent warning.")

    if current is not None and target is not None:
        delta = current - target
        if abs(delta) >= 25000:
            add("Current List Price / Market Exposure", "QUALIFIES", f"Current list price differs from the comp-supported target by {_fmt_stack_money(delta)}; tactical advice must separate comp-supported value from current buyer-action price.")
        elif low is not None and high is not None and low <= current <= high:
            add("Current List Price / Market Exposure", "CONFIRMS", "Current list price sits inside the supported range.")
    elif after_active_pricing_review:
        add("Current List Price / Market Exposure", "HUMAN REVIEW REQUIRED", "Current Market Context overlay exists but current list price was not detected.")

    overall = "CONFIRMED"
    effects = {i["effect_on_recommendation"] for i in impacts}
    if "HUMAN REVIEW REQUIRED" in effects:
        overall = "HUMAN REVIEW REQUIRED"
    elif "WEAKENS" in effects or "QUALIFIES" in effects or "MIXED" in effects:
        overall = "QUALIFIED"

    return compact_dict({
        "section_title": "Cross-Section Impact Review",
        "purpose": "Determine whether any analytical section changes, qualifies, weakens, or confirms the preliminary comp-supported recommendation.",
        "overall_cross_section_result": overall,
        "impacts": impacts,
        "rule": "Sections are not independent summaries. Each section must be allowed to affect the final recommendation, and contradictions must be explained rather than smoothed over.",
    })


def build_evidence_integrity_review(
    pricing_reconciliation: Dict[str, Any],
    comp_fit_audit: Dict[str, Any],
    cross_section_impact_review: Dict[str, Any],
    after_active_pricing_review: Dict[str, Any],
) -> Dict[str, Any]:
    status = cross_section_impact_review.get("overall_cross_section_result") or comp_fit_audit.get("audit_status") or "QUALIFIED"
    # Escalate comp-fit failure/human-review status even when cross-section review
    # summarizes it as a qualification. The report must not soften a true comp-fit
    # problem into a supportive narrative.
    if comp_fit_audit.get("audit_status") == "HUMAN REVIEW REQUIRED":
        status = "HUMAN REVIEW REQUIRED"
    target = money_or_none(pricing_reconciliation.get("recommended_list_price"))
    current = money_or_none(after_active_pricing_review.get("current_list_price"))

    required_report_behavior = []
    if status == "CONFIRMED":
        required_report_behavior.append("Tarzan may present the range as supported, while still avoiding guarantees.")
    elif status == "QUALIFIED":
        required_report_behavior.append("Tarzan must present the range as qualified by current market/comp-fit evidence and avoid false confidence.")
    else:
        required_report_behavior.append("Tarzan must not present the range as final without human Realtor review.")

    if current is not None and target is not None:
        required_report_behavior.append("Separate Comp-Supported Value from Current Market-Action / current market-position review.")

    return compact_dict({
        "section_title": "Evidence Integrity Decision",
        "mode": "Evidence Integrity Mode",
        "final_range_status": status,
        "preliminary_comp_supported_range": {
            "low": pricing_reconciliation.get("recommended_price_range_low"),
            "target": pricing_reconciliation.get("recommended_list_price"),
            "high": pricing_reconciliation.get("recommended_price_range_high"),
            "source": pricing_reconciliation.get("source"),
        },
        "current_after_active_price": current,
        "required_report_behavior": required_report_behavior,
        "permanent_rule": "Do not justify the number. Test the number. GPT may not create value or false support; it may only explain the evidence after checking it.",
    })



def build_pricing_logic_stack(
    pricing_reconciliation: Dict[str, Any],
    engine_output: Dict[str, Any],
    market_momentum: Dict[str, Any],
    market_conditions_1004mc: Dict[str, Any],
    price_sensitivity: Dict[str, Any],
    market_acceptance_repositioning_review: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the plain black-and-white stacked Pricing Logic table.

    This is not a second valuation model. It is a seller-readable worksheet that
    shows each review layer, whether a separate adjustment was applied, and why.
    Comparable-specific adjustments remain inside the comp grid/valuation model.
    """
    pricing_reconciliation = pricing_reconciliation or {}
    engine_output = engine_output or {}
    market_momentum = market_momentum or {}
    market_conditions_1004mc = market_conditions_1004mc or {}
    price_sensitivity = price_sensitivity or {}

    low = money_or_none(pricing_reconciliation.get("recommended_price_range_low"))
    high = money_or_none(pricing_reconciliation.get("recommended_price_range_high"))
    midpoint = _pricing_midpoint(pricing_reconciliation)

    time_supported = bool(
        first_available(
            market_conditions_1004mc.get("time_adjustments_supported"),
            market_conditions_1004mc.get("time_adjustments_applied"),
            engine_output.get("time_adjustments_enabled"),
        )
    )
    selected_comps = engine_output.get("selected_adjusted_comps") or []
    time_values = []
    if isinstance(selected_comps, list):
        for row in selected_comps:
            if isinstance(row, dict):
                n = money_or_none(first_available(row.get("time_adjustment"), row.get("_time_adjustment")))
                if n is not None:
                    time_values.append(n)
    time_summary = "Reviewed; no separate range-level adjustment applied."
    if time_supported or any(v != 0 for v in time_values):
        time_summary = "Time adjustments are handled in comp-specific math when the 1004MC/time trend supports them."

    rows = [
        {
            "step": 1,
            "review_item": "Comp-Supported Suggested List Range",
            "adjustment_or_result": f"{_fmt_stack_money(low)} to {_fmt_stack_money(high)}" if low is not None and high is not None else "—",
            "notes": "Starting range from selected comparable valuation support.",
        },
        {
            "step": 2,
            "review_item": "Working Midpoint Anchor",
            "adjustment_or_result": _fmt_stack_money(midpoint),
            "notes": "Internal working reference only; not a separate recommendation.",
        },
        {
            "step": 3,
            "review_item": "Comp Adjustment Totals",
            "adjustment_or_result": "Included in comp model",
            "notes": "Comparable-specific adjustments are handled separately in the comp grid.",
        },
        {
            "step": 4,
            "review_item": "Market Momentum Adjustment",
            "adjustment_or_result": "$0",
            "notes": "No separate dollar adjustment unless Active, Pending, and Closed behavior shows a clear market-momentum effect.",
        },
        {
            "step": 5,
            "review_item": "DIM / Market Acceptance Adjustment",
            "adjustment_or_result": "$0",
            "notes": "Review exposure, buyer activity, and DIM pattern; apply only when market resistance is material.",
        },
        {
            "step": 6,
            "review_item": "1004MC / Time Adjustment",
            "adjustment_or_result": "$0",
            "notes": time_summary,
        },
        {
            "step": 7,
            "review_item": "Price Sensitivity Adjustment",
            "adjustment_or_result": "$0",
            "notes": "Use only when reductions, net-close behavior, concessions, or pending speed show clear price sensitivity.",
        },
        {
            "step": 8,
            "review_item": "Feature / Property Considerations",
            "adjustment_or_result": "Qualitative review",
            "notes": "Review scarcity, condition, presentation, garage/basement utility, and competing property features.",
        },
        {
            "step": 9,
            "review_item": "Recommended Price Position",
            "adjustment_or_result": _fmt_stack_money(pricing_reconciliation.get("recommended_list_price")),
            "notes": "Final recommended position after valuation support and market considerations are reviewed.",
        },
    ]

    return {
        "section_title": "Recommended Price Logic",
        "plain_text_black_and_white": True,
        "not_a_second_valuation_model": True,
        "show_zero_adjustments_rule": "If no adjustment is applied, show $0 and explain why.",
        "comp_adjustments_are_separate_rule": "Comparable-specific adjustments remain in the valuation comp grid; this stack shows overall market/review layers.",
        "rows": rows,
    }


def build_after_active_logic_stack(
    report_routing: Dict[str, Any],
    after_active_pricing_review: Dict[str, Any],
    pricing_reconciliation: Dict[str, Any],
    listing_history_review: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a separate stacked table for current market context review.

    This remains separate from first-pass valuation. It is an IF/ELSE overlay used
    only when a listing is already exposed, reduced, relisted, expired/withdrawn,
    or has showing/market feedback.
    """
    report_routing = report_routing or {}
    after_active_pricing_review = after_active_pricing_review or {}
    pricing_reconciliation = pricing_reconciliation or {}
    listing_history_review = listing_history_review or {}

    if not report_routing.get("after_active_overlay"):
        return {}

    snapshot = report_routing.get("subject_market_snapshot") or {}
    current_price = money_or_none(first_available(after_active_pricing_review.get("current_list_price"), snapshot.get("current_price")))
    original_price = money_or_none(first_available(after_active_pricing_review.get("original_list_price"), snapshot.get("original_price")))
    dim = first_available(after_active_pricing_review.get("days_in_mls"), snapshot.get("dim"))
    target = money_or_none(pricing_reconciliation.get("recommended_list_price"))
    low = money_or_none(pricing_reconciliation.get("recommended_price_range_low"))
    high = money_or_none(pricing_reconciliation.get("recommended_price_range_high"))

    current_vs_target = None
    if current_price is not None and target is not None:
        current_vs_target = current_price - target

    exposure_note = "Review current DIM, showing activity, and buyer response."
    if dim not in (None, ""):
        exposure_note = f"Current visible DIM/exposure marker: {dim}. Review against local pending/sold speed."
    if listing_history_review.get("prior_exposure_or_relist_detected"):
        exposure_note = "Prior ListingID/relist history supplied; current visible DIM may understate cumulative exposure."

    rows = [
        {
            "step": 1,
            "review_item": "Current List Price",
            "adjustment_or_result": _fmt_stack_money(current_price),
            "notes": "Starting point for current market context review; not the same as first-pass valuation. Source: " + str(after_active_pricing_review.get("current_list_price_source") or "not supplied") + (". " + str(after_active_pricing_review.get("current_price_conflict_warning")) if after_active_pricing_review.get("current_price_conflict_warning") else ""),
        },
        {
            "step": 2,
            "review_item": "Original-to-Current Price Movement",
            "adjustment_or_result": "$0" if not (original_price and current_price) else _fmt_stack_money(current_price - original_price),
            "notes": "Shows prior seller repositioning already taken, if original price is known.",
        },
        {
            "step": 3,
            "review_item": "Current Price vs Recommended Position",
            "adjustment_or_result": "$0" if current_vs_target in (None, 0) else _fmt_stack_money(current_vs_target),
            "notes": "Measures current list price against the comp-supported recommended position.",
        },
        {
            "step": 4,
            "review_item": "DIM / Showing Conversion Review",
            "adjustment_or_result": "$0",
            "notes": exposure_note,
        },
        {
            "step": 5,
            "review_item": "Listing History / Relist Exposure Review",
            "adjustment_or_result": "$0",
            "notes": listing_history_review.get("summary") or "No prior ListingID/relist history supplied.",
        },
        {
            "step": 6,
            "review_item": "Condition / Presentation Review",
            "adjustment_or_result": "$0",
            "notes": "Use Realtor notes/photos/showing feedback when presentation, condition, or buyer objections are material.",
        },
        {
            "step": 7,
            "review_item": "Current Market Context Review",
            "adjustment_or_result": after_active_pricing_review.get("current_price_position") or "Review required",
            "notes": "If market response contradicts closed-comp support, current buyer response controls next-action advice.",
        },
    ]

    return {
        "section_title": "Current Market Context Logic Stack",
        "plain_text_black_and_white": True,
        "separate_if_else_overlay": True,
        "not_part_of_first_pass_valuation_logic": True,
        "show_zero_adjustments_rule": "If no separate dollar adjustment is applied, show $0 and explain the review item.",
        "rows": rows,
    }

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
            "closed_count_total_0_365_pull": market_momentum.get("closed_count_total_0_365_pull"),
            "closed_count_last_90_days": market_momentum.get("closed_count_last_90_days"),
            "recent_90_day_start_date": market_momentum.get("recent_90_day_start_date"),
            "recent_90_day_end_date": market_momentum.get("recent_90_day_end_date"),
            "recent_90_day_months_used": market_momentum.get("recent_90_day_months_used"),
            "monthly_closed_sales_rhythm": market_momentum.get("monthly_closed_sales_rhythm"),
            "average_dim_active": market_momentum.get("average_dim_active"),
            "average_dim_pending": market_momentum.get("average_dim_pending"),
            "closed_sales_min_close_date": market_momentum.get("closed_sales_min_close_date"),
            "closed_sales_max_close_date": market_momentum.get("closed_sales_max_close_date"),
            "closed_sales_months_covered": market_momentum.get("closed_sales_months_covered_rounded") or market_momentum.get("closed_sales_months_covered"),
            "average_monthly_closed_sales": market_momentum.get("average_monthly_closed_sales"),
            "primary_months_of_inventory": market_momentum.get("primary_months_of_inventory") or market_momentum.get("projected_moi_closed_only"),
            "primary_moi_formula": market_momentum.get("primary_moi_formula") or "Active listings ÷ latest 90-day average monthly Closed sales",
            "current_demand_pressure_moi": market_momentum.get("current_demand_pressure_moi") or market_momentum.get("projected_moi_absorption_weighted"),
            "current_demand_pressure_formula": market_momentum.get("current_demand_pressure_formula") or "Active listings ÷ (Pending listings + latest 90-day average monthly Closed sales)",
            "projected_moi_absorption_weighted": market_momentum.get("projected_moi_absorption_weighted"),
            "projected_moi_closed_only": market_momentum.get("projected_moi_closed_only"),
            "projected_moi_range": market_momentum.get("projected_moi_range"),
            "closed_sales_pace_rule": market_momentum.get("closed_sales_pace_rule"),
            "moi_reporting_rule": market_momentum.get("moi_reporting_rule") or (
                "Use Closed-only MOI as the primary seller-facing supply/absorption number. "
                "Use the pending-inclusive formula only as a secondary current-demand pressure indicator."
            ),
            "source": market_momentum.get("source"),
            "status": market_momentum.get("status"),
            "important_limitation": market_momentum.get("important_limitation"),
            "seller_decision_framework": (
                "Competition should be explained through Pricing, Condition, Terms, and Timing. "
                "Active listings are the current lineup buyers can choose from. The seller must decide where this home belongs in that lineup based on condition, presentation, and how firmly they want to hold price and terms."
            ),
            "closed_sales_pace_reporting_rule": (
                "When the 1004MC / Competition Market File includes up to 365 days of Closed sales, keep that full-year pull for monthly rhythm/trend review, "
                "but calculate current absorption from the most recent 90 days of Closed sales divided by 3."
            ),
            "primary_moi_reporting_rule": (
                "For seller-facing reporting, use Closed-only MOI as the primary Months of Inventory number: "
                "Active listings divided by the latest 90-day average monthly Closed sales. "
                "The pending-inclusive formula may be shown as a secondary demand-pressure indicator only if it helps explain near-term buyer activity."
            ),
            "negotiation_leverage_rule": (
                "When price and condition align with the active competition, the seller is more likely to hold stronger terms. "
                "When price is high relative to condition or presentation, buyers gain leverage through concessions, inspection objections, termination risk, or simply choosing another active property."
            ),
            "reporting_rule": (
                "Active, Coming Soon, and Pending listings influence launch posture, buyer alternatives, pricing risk, and negotiation leverage. "
                "They do not create the closed-comp value range, but they affect how buyers compare this listing today."
            ),
        }
    )


def build_market_acceptance_repositioning_review(
    current_competition_check: Dict[str, Any],
    market_momentum: Dict[str, Any],
    price_sensitivity: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a separate market-acceptance section so GPT does not bury it inside Momentum."""
    current_competition_check = current_competition_check or {}
    market_momentum = market_momentum or {}
    price_sensitivity = price_sensitivity or {}

    closed_adjustment = price_sensitivity.get("closed_last_90_price_adjustment_behavior") or {}
    active_adjustment = price_sensitivity.get("active_price_adjustment_behavior") or {}
    pending_adjustment = price_sensitivity.get("pending_price_adjustment_behavior") or {}

    return compact_dict(
        {
            "section_label": "Market Acceptance / Repositioning Review",
            "purpose": (
                "Separate from valuation and separate from Momentum. This section asks whether buyers are accepting the current price/condition/terms position, "
                "or whether the listing may require a tactical repositioning review."
            ),
            "not_automatic_price_cut_rule": (
                "Do not arbitrarily recommend an adjustment. First read buyer behavior, active competition, showing response, price reductions, concessions, seller-net behavior, condition, and terms."
            ),
            "seller_psychology_rule": (
                "Sellers often worry that a price reduction signals weakness. Explain the difference between a late reactive reduction after market rejection and an early data-supported strategic repositioning."
            ),
            "active_lineup": {
                "active_count": current_competition_check.get("active_count"),
                "average_days_in_mls_active": current_competition_check.get("average_dim_active"),
                "active_reduction_rate_percent": active_adjustment.get("price_reduction_rate_percent"),
                "active_average_reduction_when_reduced": active_adjustment.get("average_reduction_amount_when_reduced"),
            },
            "pending_behavior": {
                "pending_count": current_competition_check.get("pending_count"),
                "average_days_in_mls_pending": current_competition_check.get("average_dim_pending"),
                "pending_reduction_rate_percent": pending_adjustment.get("price_reduction_rate_percent"),
                "pending_average_reduction_when_reduced": pending_adjustment.get("average_reduction_amount_when_reduced"),
            },
            "closed_last_90_behavior": {
                "closed_sales_reviewed": price_sensitivity.get("closed_sales_reviewed"),
                "closed_sales_window": price_sensitivity.get("closed_sales_window"),
                "latest_90_start_date": price_sensitivity.get("latest_90_start_date"),
                "latest_90_end_date": price_sensitivity.get("latest_90_end_date"),
                "mls_list_price_reduction_rate_percent": closed_adjustment.get("price_reduction_rate_percent"),
                "average_reduction_amount_when_reduced": closed_adjustment.get("average_reduction_amount_when_reduced"),
                "average_dim_reduced": closed_adjustment.get("average_dim_reduced"),
                "average_dim_not_reduced": closed_adjustment.get("average_dim_not_reduced"),
                "net_below_original_rate_percent": price_sensitivity.get("net_below_original_rate_percent"),
                "seller_concession_rate_percent": price_sensitivity.get("seller_concession_rate_percent"),
                "average_concession_when_present": price_sensitivity.get("average_concession_when_present"),
            },
            "signal": price_sensitivity.get("price_sensitivity_level"),
            "seller_decision_translation": (
                "Use this section to explain how current buyer behavior affects price, condition, terms, timing, and leverage. "
                "A recommended range may be comp-supported, but the market acceptance review tells whether buyers are actually responding to that position."
            ),
            "first_7_to_14_day_rule": (
                "If showings, second looks, disclosure requests, agent questions, or offer activity are weak in the first 7–14 days after launch/repositioning, review price, condition, presentation, and terms before the listing becomes stale."
            ),
        }
    )


def build_price_sensitivity_seller_net_behavior(price_sensitivity: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the Tarzan support section for report_input."""
    price_sensitivity = price_sensitivity or {}
    if not price_sensitivity:
        return {}
    return compact_dict(
        {
            "section_label": "Price Sensitivity & Seller Net Behavior",
            "source": price_sensitivity.get("source"),
            "status": price_sensitivity.get("status"),
            "purpose": price_sensitivity.get("purpose") or (
                "Shows how often sellers had to reposition, concede, or net below original list before buyers accepted properties in the reviewed market."
            ),
            "closed_sales_window": price_sensitivity.get("closed_sales_window"),
            "closed_sales_reviewed": price_sensitivity.get("closed_sales_reviewed"),
            "latest_90_start_date": price_sensitivity.get("latest_90_start_date"),
            "latest_90_end_date": price_sensitivity.get("latest_90_end_date"),
            "active_price_adjustment_behavior": price_sensitivity.get("active_price_adjustment_behavior"),
            "pending_price_adjustment_behavior": price_sensitivity.get("pending_price_adjustment_behavior"),
            "closed_last_90_price_adjustment_behavior": price_sensitivity.get("closed_last_90_price_adjustment_behavior"),
            "closed_below_original_rate_percent": price_sensitivity.get("closed_below_original_rate_percent"),
            "net_below_original_rate_percent": price_sensitivity.get("net_below_original_rate_percent"),
            "seller_concession_rate_percent": price_sensitivity.get("seller_concession_rate_percent"),
            "average_concession_when_present": price_sensitivity.get("average_concession_when_present"),
            "seller_net_result_buckets": price_sensitivity.get("seller_net_result_buckets"),
            "price_sensitivity_level": price_sensitivity.get("price_sensitivity_level"),
            "repositioning_consideration": price_sensitivity.get("repositioning_consideration"),
            "seller_psychology_note": price_sensitivity.get("seller_psychology_note"),
            "reporting_rule": (
                "This is a pricing behavior snapshot, not an appraisal. It should support a market-acceptance conversation and possible repositioning review, not an automatic value cut."
            ),
        }
    )




def analyze_listing_history_notes(listing_history_notes: Optional[str]) -> Dict[str, Any]:
    """Summarize Realtor-pasted MLS listing-history / relist notes.

    MLS exports often show the current ListingID only. Prior expired/cancelled ListingIDs
    can make a listing look fresh unless the agent pastes the history. This helper keeps
    that homework visible for GPT and the seller-facing report.
    """
    text = str(listing_history_notes or "").strip()
    if not text:
        return {
            "provided": False,
            "summary": "No prior ListingID / MLS listing-history notes supplied.",
            "data_limitation": (
                "Cumulative market exposure may be understated if the property was previously listed under another ListingID."
            ),
        }

    listing_ids = sorted(set(re.findall(r"(?i)ListingID\s*:\s*([0-9]+)", text)))
    statuses = sorted(set(s.strip().title() for s in re.findall(r"(?i)Sts\s*:\s*([A-Za-z ]+)", text) if s.strip()))
    # Practical extraction: collect the last numeric value on event rows when present.
    event_days = []
    for line in text.splitlines():
        # MLS history event rows usually begin with an effective date and end with Days in MLS.
        if not re.match(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\b", line):
            continue
        parts = line.strip().split()
        if not parts:
            continue
        last = parts[-1]
        if last.isdigit() and re.search(r"(?i)(New Listing|Price Decrease|Expired|Coming Soon|ACT|EXP|CSN)", line):
            try:
                event_days.append(int(last))
            except Exception:
                pass

    price_changes = re.findall(r"\$[0-9,]+\s*->\s*\$[0-9,]+", text)
    prices = []
    for value in re.findall(r"\$[0-9,]+", text):
        try:
            prices.append(float(value.replace("$", "").replace(",", "")))
        except Exception:
            pass

    prior_exposure = any(s.lower() in {"expired", "withdrawn", "cancelled", "canceled"} for s in statuses) or len(listing_ids) > 1
    relist_pattern = bool(re.search(r"(?i)(expired|withdrawn|cancelled|canceled|relist|re-listed|new listing)", text)) and len(listing_ids) > 1

    max_days_seen = max(event_days) if event_days else None
    # Sum the max DIM per ListingID block when possible.
    block_exposure = []
    blocks = re.split(r"(?i)(?=ListingID\s*:)", text)
    for block in blocks:
        if not block.strip():
            continue
        block_days = []
        for line in block.splitlines():
            if not re.match(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\b", line):
                continue
            last = line.strip().split()[-1] if line.strip().split() else ""
            if last.isdigit() and re.search(r"(?i)(New Listing|Price Decrease|Expired|Coming Soon|ACT|EXP|CSN)", line):
                block_days.append(int(last))
        if block_days:
            block_exposure.append(max(block_days))
    cumulative_dim_estimate = sum(block_exposure) if block_exposure else max_days_seen

    return {
        "provided": True,
        "listing_ids_found": listing_ids,
        "statuses_found": statuses,
        "prior_exposure_or_relist_detected": prior_exposure,
        "relist_freshness_risk_detected": relist_pattern,
        "price_change_events_found": price_changes,
        "highest_price_seen": max(prices) if prices else None,
        "lowest_price_seen": min(prices) if prices else None,
        "max_days_in_mls_seen_on_any_listing": max_days_seen,
        "estimated_cumulative_days_in_mls_from_pasted_history": cumulative_dim_estimate,
        "summary": (
            "Prior ListingID / relist history supplied. Treat current ListingID DIM as incomplete exposure context."
            if prior_exposure else
            "Listing history supplied, but no clear prior expired/withdrawn ListingID was detected."
        ),
        "seller_facing_rule": (
            "If prior MLS exposure exists under another ListingID, do not describe the listing as fresh based only on the current ListingID. "
            "Explain cumulative exposure carefully: relisting can reset visible Days in MLS, but buyers and agents may still recognize the property and prior pricing."
        ),
        "raw_notes": text,
    }

def build_additional_notes_provided(
    realtor_notes: Optional[str],
    buyer_consideration_notes: Optional[str],
    manual_pricing: Optional[Dict[str, Any]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    listing_history_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Preserve one first-run report notes field for Tarzan.

    v20.5.3 intentionally reduces Module 5 Report Context to one notes field.
    Larger showing-history / after-active context belongs in Retrospect later.
    """
    manual_pricing = manual_pricing or {}
    additional_context = additional_context or {}

    def clean_text(value: Any) -> str:
        return str(value or "").strip()

    report_notes = clean_text(
        manual_pricing.get("report_notes")
        or additional_context.get("field_intelligence_notes")
        or realtor_notes
        or manual_pricing.get("realtor_notes")
    )

    categories: List[Dict[str, str]] = []
    if report_notes:
        categories.append({
            "label": "Report Notes / Field Intelligence",
            "notes": report_notes,
        })

    return compact_dict({
        "section_label": "Additional Notes Provided",
        "include_in_every_report": bool(categories),
        "purpose": (
            "Preserve the single Realtor/user-supplied pre-appointment notes field so Tarzan can confirm it was considered. "
            "These notes are field intelligence or verification context; they do not silently rewrite the comp-adjustment math."
        ),
        "categories": categories,
        "reporting_rule": (
            "If supplied, show the Report Notes / Field Intelligence category in Tarzan. "
            "If notes are unclear or unverified, state that they require Realtor/field confirmation rather than using them as hard value adjustments. "
            "Detailed after-active showing logs, relist histories, and tactical pricing review belong in ICHIBAN Retrospect, not this first-run Tarzan branch."
        ),
        "support_files": [],
    })


def build_tarzan_report_standards(report_mode: str, report_date: str) -> Dict[str, Any]:
    """Hard-save the current Tarzan-first report standard into report_input.

    v20.5.3 keeps first-run valuation focused on Tarzan only. BBC and
    Retrospect remain paused until this objective valuation branch is stable.
    """
    return {
        "version": "v20_5_3_tarzan_single_notes_standard",
        "report_date": report_date,
        "report_mode": "tarzan_valuation_analysis",
        "active_output": "Tarzan Valuation Analysis",
        "paused_outputs": ["BBC Seller Interpretation", "ICHIBAN Retrospect / Current Market Context"],
        "tarzan_standard": {
            "purpose": "Detailed objective valuation analysis and supporting evidence record.",
            "content": "Subject facts, selected comps, appraisal-style adjustments, adjusted comp range, comparable fit audit, range reconciliation, market momentum, absorption, concessions/net behavior, 1004MC/time review, price sensitivity, data verification, one optional Report Notes / Field Intelligence field, and final status.",
            "voice": "Informed, educated, objective, Realtor-useful, and valuation-disciplined. No seller-facing fluff and no loose buyer-emotion speculation.",
            "locked_values_meaning": "Supplied comp-adjustment math is the factual valuation base. Do not invent a different range, but do qualify whether the range is confirmed, qualified, incomplete, or requires human review.",
            "notes_standard": "First-run Tarzan uses one Report Notes / Field Intelligence field only. Notes qualify or verify evidence; they do not silently rewrite comp math. Detailed after-active showing history belongs in Retrospect later.",
        },
        "required_sections": [
            "Subject and Data Status",
            "Valuation Summary",
            "Comparable Selection and Fit Audit",
            "Appraisal-Style Adjustment Review",
            "Adjusted Comparable Evidence",
            "Range Reconciliation",
            "Market Momentum and Absorption",
            "Active/Pending/Closed Behavior",
            "Concessions and Seller-Net Behavior",
            "1004MC / Time Review",
            "Price Sensitivity Review",
            "Realtor Notes / Field Intelligence, if supplied",
            "Data Verification and Limitations",
            "Final Tarzan Status: CONFIRMED / QUALIFIED / INCOMPLETE / HUMAN REVIEW REQUIRED",
        ],
        "forbidden_behavior": [
            "Do not write a Tarzan seller-facing report in this branch.",
            "Do not write ICHIBAN Retrospect / Current Market Context tactical review in this branch.",
            "Do not use BBC Seller Point boxes in Tarzan.",
            "Do not defend the range blindly.",
            "Do not invent comps, facts, or adjustments.",
            "Do not split first-run context into multiple note categories.",
        ],
    }


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
    raw_price_sensitivity = engine_output.get("price_sensitivity_and_seller_net_behavior") or {}
    market_conditions_1004mc = first_available(
        engine_output.get("market_conditions_1004mc"),
        valuation_input_package.get("one_hundred_four_mc_summary"),
        {},
    )
    market_workflow_rule = first_available(
        engine_output.get("market_workflow_rule"),
        valuation_input_package.get("market_workflow_rule"),
        additional_context.get("market_workflow_rule"),
        {},
    )
    market_file_roles = first_available(
        engine_output.get("market_file_roles"),
        valuation_input_package.get("market_file_roles"),
        additional_context.get("market_file_roles"),
        {},
    )
    report_language_rule = first_available(
        valuation_input_package.get("report_language_rule"),
        market_workflow_rule.get("report_language_rule") if isinstance(market_workflow_rule, dict) else None,
        additional_context.get("report_language_rule"),
        "The value range is based on closed comparable evidence. The market momentum section reviews a broader competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction.",
    )
    # There is now one report standard. Older report_type/report_mode values are ignored
    # except for backward-compatible saved JSON handling inside report routing.
    report_type = "Tarzan Valuation Analysis"
    report_mode = DEFAULT_REPORT_VERSION
    report_date = first_available(
        additional_context.get("report_date"),
        manual_pricing.get("report_date"),
        datetime.now().date().isoformat(),
    )
    current_competition_check = build_current_competition_check(market_momentum)
    price_sensitivity_seller_net_behavior = build_price_sensitivity_seller_net_behavior(raw_price_sensitivity)
    market_acceptance_repositioning_review = build_market_acceptance_repositioning_review(
        current_competition_check=current_competition_check,
        market_momentum=market_momentum,
        price_sensitivity=price_sensitivity_seller_net_behavior,
    )
    pricing_reconciliation = build_pricing_reconciliation(manual_pricing, engine_output)
    ruler_range = build_ruler_range(
        pricing_reconciliation=pricing_reconciliation,
        selected_comparable_evidence_range=selected_comparable_evidence_range,
        online_estimated_value=online_estimated_value,
    )

    pricing_logic_stack = build_pricing_logic_stack(
        pricing_reconciliation=pricing_reconciliation,
        engine_output=engine_output,
        market_momentum=market_momentum,
        market_conditions_1004mc=market_conditions_1004mc,
        price_sensitivity=raw_price_sensitivity,
        market_acceptance_repositioning_review=market_acceptance_repositioning_review,
    )


    agent_review_inputs = {
        "section_title": "Agent Review Inputs",
        "placement": "Immediately after Recommended Range and before Seller Summary",
        "purpose": (
            "Printed Realtor reminder/circle-able report template body section. "
            "Used to help position the property within the recommended range based on visible condition, buyer confidence, inspection leverage, and seller terms. "
            "These items are not automatic value reductions."
        ),
        "upgrades_condition": {
            "label": "Upgrades / Condition",
            "instruction": "Circle one",
            "options": [
                "Ultra Low",
                "Low",
                "Medium Low",
                "Medium",
                "Medium High",
                "High",
                "Fully Remodeled",
            ],
            "interpretation": {
                "Medium": "Average / typical market condition",
                "Medium High": "Above-average condition or updates, but not fully remodeled",
                "High": "Strong updated condition",
                "Fully Remodeled": "Substantially updated throughout",
            },
        },
        "buyer_confidence_risk_items": {
            "label": "Buyer Confidence / Risk Items",
            "instruction": "Circle / mark any that should be considered before pricing, launch, or negotiation strategy",
            "items": [
                "Roof",
                "Sewer scope",
                "Radon mitigation",
                "HVAC age / serviceability",
                "Smoke / odor concern",
                "Water intrusion / basement moisture",
                "Electrical / plumbing concerns",
                "Structural concerns",
                "Major deferred maintenance",
            ],
        },
        "seller_facing_rule": (
            "A property may look updated but still lose seller leverage if buyers perceive unresolved cost, system, odor, moisture, structural, or inspection risk. "
            "Completed maintenance, documentation, and clear preparation can help the seller hold firmer terms; unresolved uncertainty can create buyer leverage through concessions, inspection objections, termination risk, or choosing another active listing."
        ),
    }

    listing_history_notes = ""  # v20.5.3: first-run Tarzan uses one notes field; detailed listing history moves to Retrospect.
    listing_history_review = analyze_listing_history_notes(listing_history_notes)

    additional_notes_provided = build_additional_notes_provided(
        realtor_notes=realtor_notes or manual_pricing.get("realtor_notes") or "",
        buyer_consideration_notes=buyer_consideration_notes or manual_pricing.get("buyer_consideration_notes") or "",
        manual_pricing=manual_pricing,
        additional_context=additional_context,
        listing_history_notes=listing_history_notes,
    )

    report_notes_for_context = (
        manual_pricing.get("report_notes")
        or additional_context.get("field_intelligence_notes")
        or realtor_notes
        or manual_pricing.get("realtor_notes")
        or ""
    )
    showing_activity_notes = str(report_notes_for_context or "")

    market_summary_for_routing = {
        "active_records": (market_momentum or {}).get("active_count"),
        "coming_soon_records": (market_momentum or {}).get("coming_soon_count"),
        "pending_records": (market_momentum or {}).get("pending_count"),
        "closed_records": (market_momentum or {}).get("closed_count"),
        "records": engine_output.get("market_rows_loaded") or valuation_input_package.get("market_rows"),
    }

    routing_subject_profile = dict(subject_profile or {})
    subject_market_snapshot = engine_output.get("subject_market_snapshot") or {}
    if isinstance(subject_market_snapshot, dict):
        if subject_market_snapshot.get("status"):
            routing_subject_profile["status"] = subject_market_snapshot.get("status")
        if subject_market_snapshot.get("current_price"):
            routing_subject_profile["current_price"] = subject_market_snapshot.get("current_price")
        if subject_market_snapshot.get("original_price"):
            routing_subject_profile["original_list_price"] = subject_market_snapshot.get("original_price")
        if subject_market_snapshot.get("days_in_mls") is not None:
            routing_subject_profile["days_in_mls"] = subject_market_snapshot.get("days_in_mls")

    report_routing = resolve_report_routing(
        requested_report_version=additional_context.get("report_version") or report_mode or report_type,
        input_mode=additional_context.get("input_mode") or "hybrid",
        subject_property=routing_subject_profile,
        market_df=additional_context.get("market_df_for_routing"),
        market_summary=market_summary_for_routing,
        showing_activity_notes=showing_activity_notes,
    )

    if listing_history_review.get("prior_exposure_or_relist_detected"):
        report_routing["after_active_overlay"] = True
        report_routing["after_active_reason"]["listing_history_trigger"] = True
        report_routing["range_policy"] = [
            "Closed-Comp Supported Range",
            "Current List Price Position",
            "Cumulative MLS Exposure / Relist History",
            "Showing Conversion Range",
            "Recommended Next Action",
        ]
        warning_text = "Prior ListingID / relist history supplied; current ListingID DIM may understate cumulative exposure."
        if warning_text not in report_routing["warnings"]:
            report_routing["warnings"].append(warning_text)

    if subject_market_snapshot and not report_routing.get("subject_market_snapshot", {}).get("current_price"):
        report_routing["subject_market_snapshot"].update(
            {
                "status": subject_market_snapshot.get("status"),
                "current_price": subject_market_snapshot.get("current_price"),
                "original_price": subject_market_snapshot.get("original_price"),
                "previous_price": subject_market_snapshot.get("previous_price"),
                "dim": subject_market_snapshot.get("days_in_mls"),
                "price_reduction_detected": subject_market_snapshot.get("price_reduction_detected"),
            }
        )
        if subject_market_snapshot.get("status") in {"active", "coming soon", "pending", "withdrawn", "expired", "cancelled", "canceled"}:
            report_routing["after_active_overlay"] = True
            report_routing["after_active_reason"]["subject_status_trigger"] = True
            report_routing["range_policy"] = [
                "Closed-Comp Supported Range",
                "Current List Price Position",
                "Showing Conversion Range",
                "Recommended Next Action",
            ]
            if "Current market context detected; treat only as context in the Tarzan-first valuation branch." not in report_routing["warnings"]:
                report_routing["warnings"].append("Current market context detected; treat only as context in the Tarzan-first valuation branch.")

    report_mode = "tarzan_valuation_analysis"
    report_routing["resolved_report_version"] = report_mode
    report_routing["resolved_label"] = "Tarzan Valuation Analysis"
    report_routing["after_active_overlay"] = False
    tarzan_report_standards = build_tarzan_report_standards(report_mode=report_mode, report_date=str(report_date))

    after_active_pricing_review = {}
    if False and report_routing.get("after_active_overlay"):
        snapshot = report_routing.get("subject_market_snapshot") or {}
        current_price, current_price_source = _first_money_with_source(
            ("user-entered current list price", manual_pricing.get("after_active_current_list_price")),
            ("user-entered current list price", manual_pricing.get("current_list_price")),
            ("additional context current list price", additional_context.get("after_active_current_list_price")),
            ("active subject row current price", snapshot.get("current_price")),
        )
        snapshot_current_price = money_or_none(snapshot.get("current_price"))
        current_price_conflict_warning = None
        if current_price is not None and snapshot_current_price is not None and current_price != snapshot_current_price:
            current_price_conflict_warning = (
                f"Conflicting current list prices found: { _fmt_stack_money(current_price) } from {current_price_source} "
                f"versus { _fmt_stack_money(snapshot_current_price) } from active subject row. User-entered/current override controls current market context math."
            )
        recommended_low = money_or_none(pricing_reconciliation.get("recommended_price_range_low"))
        recommended_high = money_or_none(pricing_reconciliation.get("recommended_price_range_high"))
        recommended_target = money_or_none(pricing_reconciliation.get("recommended_list_price"))

        position = "current price not detected"
        if current_price is not None and recommended_low is not None and recommended_high is not None:
            if current_price > recommended_high:
                position = "current list price is above the closed-comp supported recommended range"
            elif current_price < recommended_low:
                position = "current list price is below the closed-comp supported recommended range"
            else:
                position = "current list price is inside the closed-comp supported recommended range"

        after_active_pricing_review = {
            "section_title": "Current Market Context Review",
            "active_overlay": True,
            "purpose": (
                "When the subject is already exposed to the market, current buyer response becomes evidence. "
                "Closed-comp support must be separated from showing conversion and next-action advice."
            ),
            "current_list_price": current_price,
            "current_list_price_source": current_price_source,
            "current_price_conflict_warning": current_price_conflict_warning,
            "original_list_price": money_or_none(snapshot.get("original_price")),
            "previous_list_price": money_or_none(snapshot.get("previous_price")),
            "days_in_mls": snapshot.get("dim"),
            "price_reduction_detected": snapshot.get("price_reduction_detected"),
            "listing_history_review": listing_history_review,
            "closed_comp_supported_recommended_low": recommended_low,
            "closed_comp_supported_recommended_target": recommended_target,
            "closed_comp_supported_recommended_high": recommended_high,
            "current_price_position": position,
            "seller_facing_rule": (
                "If the current price is below the closed-comp supported range but activity is weak, do not automatically raise the recommendation. "
                "Explain that buyer urgency may be affected by active competition, condition, presentation, incentives, unfinished work, payment pressure, taxes/HOA, relist/cumulative exposure, or data/adjustment caveats."
            ),
        }

    after_active_logic_stack = build_after_active_logic_stack(
        report_routing=report_routing,
        after_active_pricing_review=after_active_pricing_review,
        pricing_reconciliation=pricing_reconciliation,
        listing_history_review=listing_history_review,
    )

    pre_gpt_realtor_notes_review = {
        "section_title": "Pre-GPT Realtor Notes Review",
        "required_before_tarzan_generation": False,
        "purpose": (
            "Capture one optional pre-appointment Report Notes / Field Intelligence field before the Tarzan valuation report is generated. "
            "The field may include seller-visit facts, condition concerns, known improvements, odor/fence issues, or other verification context. "
            "It is not a substitute for a future Retrospect showing-history/tactical review."
        ),
        "report_notes_supplied": bool(str(report_notes_for_context or "").strip()),
        "realtor_notes_supplied": bool(str(report_notes_for_context or "").strip()),
        "showing_feedback_notes_supplied": False,
        "listing_history_notes_supplied": False,
        "listing_history_review": listing_history_review,
        "buyer_consideration_notes_supplied": False,
        "after_active_overlay": bool(report_routing.get("after_active_overlay")),
        "rule": (
            "For first-run Tarzan, one notes field is used as field intelligence. It may qualify the analysis, but it must not silently rewrite comp math. "
            "Detailed showing feedback, cumulative exposure, relist strategy, and tactical price movement belong in ICHIBAN Retrospect later."
        ),
        "missing_notes_warning": (
            "No Report Notes / Field Intelligence were supplied. This is acceptable for a pre-appointment first run, but condition or seller-visit facts should be added when known."
            if not str(report_notes_for_context or "").strip()
            else ""
        ),
    }

    comparable_fit_audit = build_comparable_fit_audit(
        engine_output=engine_output,
        subject_profile=subject_profile,
    )
    cross_section_impact_review = build_cross_section_impact_review(
        pricing_reconciliation=pricing_reconciliation,
        comp_fit_audit=comparable_fit_audit,
        market_momentum=market_momentum,
        price_sensitivity=price_sensitivity_seller_net_behavior,
        market_acceptance_repositioning_review=market_acceptance_repositioning_review,
        after_active_pricing_review=after_active_pricing_review,
    )
    evidence_integrity_review = build_evidence_integrity_review(
        pricing_reconciliation=pricing_reconciliation,
        comp_fit_audit=comparable_fit_audit,
        cross_section_impact_review=cross_section_impact_review,
        after_active_pricing_review=after_active_pricing_review,
    )

    report_input = {
        "report_input_version": CURRENT_REPORT_INPUT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "report_date": str(report_date),
        "purpose": "Structured GPT handoff for ICHIBAN INSIGHT Tarzan Valuation Analysis generation.",
        "workflow_boundary": {
            "math_first_gpt_second": True,
            "gpt_may_explain_but_not_recalculate": True,
            "private_logic_should_not_be_exposed_in_seller_report": True,
            "tarzan_goal": "Detailed objective Realtor valuation analysis with subject facts, comp adjustment support, comparable-fit qualification, range reconciliation, market momentum, absorption, concessions/net behavior, 1004MC/time review, and data verification.",
        },
        "source_metadata": compact_dict(
            {
                "module_4_wrapper": wrapper_metadata,
                "engine_version": engine_output.get("engine_version"),
                "engine_status": engine_output.get("engine_status"),
                "engine_scope": engine_output.get("engine_scope"),
                "market_rows_loaded": engine_output.get("market_rows_loaded") or valuation_input_package.get("market_rows"),
                "valuation_comp_rows_loaded": engine_output.get("valuation_comp_rows_loaded") or (valuation_input_package.get("valuation_comp_file") or {}).get("rows"),
                "competition_market_rows_loaded": engine_output.get("competition_market_rows_loaded") or (valuation_input_package.get("competition_market_file") or {}).get("rows"),
                "closed_rows_available": engine_output.get("closed_rows_available"),
                "comp_rows_scored": engine_output.get("comp_rows_scored"),
                "comp_rows_selected": engine_output.get("comp_rows_selected"),
            }
        ),
        "report_package": {
            "report_type": report_type,
            "report_mode": report_mode,
            "report_version": report_mode,
            "report_language_rule": report_language_rule,
            "market_workflow_rule": market_workflow_rule,
            "market_file_roles": market_file_roles,
            "valuation_comp_file": valuation_input_package.get("valuation_comp_file") or {},
            "competition_market_file": valuation_input_package.get("competition_market_file") or {},
            "report_routing": report_routing,
        },
        "report_routing": report_routing,
        "pre_gpt_realtor_notes_review": pre_gpt_realtor_notes_review,
        "listing_history_review": listing_history_review,
        "after_active_pricing_review": after_active_pricing_review,
        "subject_property_summary": subject_profile,
        "online_estimates": online_estimated_value,
        "selected_comparable_evidence_range": selected_comparable_evidence_range,
        "selected_adjusted_comps": engine_output.get("selected_adjusted_comps") or [],
        "comp_statistics": engine_output.get("comp_statistics") or {},
        "comparable_fit_audit": comparable_fit_audit,
        "cross_section_impact_review": cross_section_impact_review,
        "evidence_integrity_review": evidence_integrity_review,
        "current_competition_check": current_competition_check,
        "market_acceptance_repositioning_review": market_acceptance_repositioning_review,
        "market_momentum": market_momentum,
        "price_sensitivity_seller_net_behavior": price_sensitivity_seller_net_behavior,
        "market_conditions_1004mc": market_conditions_1004mc,
        "pricing_reconciliation": pricing_reconciliation,
        "pricing_logic_stack": pricing_logic_stack,
        "after_active_logic_stack": after_active_logic_stack,
        "ruler_range": ruler_range,
        "agent_review_inputs": agent_review_inputs,
        "tarzan_report_standards": tarzan_report_standards,
        "additional_notes_provided": additional_notes_provided,
        "report_notes": report_notes_for_context,
        "realtor_notes": report_notes_for_context,
        "buyer_consideration_notes": "",
        "listing_history_notes": "",
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
            "baseline_style": "v20.5 Tarzan-first valuation analysis branch. Tarzan seller interpretation and Retrospect tactical review are paused.",
            "package_structure": "Generate one detailed Tarzan Valuation Analysis from the structured evidence. Do not create BBC, Seller Point boxes, or Retrospect tactical review in this branch.",
            "locked_section_order": [
                "Subject and Data Status",
                "Valuation Summary",
                "Comparable Selection and Fit Audit",
                "Appraisal-Style Adjustment Review",
                "Adjusted Comparable Evidence",
                "Range Reconciliation",
                "Market Momentum and Absorption",
                "Active / Pending / Closed Behavior",
                "Concessions and Seller-Net Behavior",
                "1004MC / Time Review",
                "Price Sensitivity Review",
                "Realtor Notes / Field Intelligence, if supplied",
                "Data Verification and Limitations",
                "Methodology / Disclaimer",
                "Final Tarzan Status",
            ],
            "include_ruler_range": True,
            "include_agent_review_inputs": False,
            "include_pricing_logic_stack": True,
            "include_after_active_overlay": False,
            "include_after_active_logic_stack_in_tarzan_after_active_section": False,
            "include_market_acceptance_repositioning_review": True,
            "include_price_sensitivity_seller_net_behavior": True,
            "include_market_momentum_near_recommended_range": True,
            "calculate_closed_sales_pace_from_actual_close_date_span": True,
            "separate_current_competition_from_momentum": True,
            "distance_from_subject_policy": "When distance-from-subject fields are available, include them; do not invent distances.",
            "main_comp_table_policy": "Address, closed/net price, concessions, close date, Days in MLS, total adjustments, and total adjusted price.",
            "adjustment_detail_policy": "Explain appraisal-style adjustment categories and why comps were adjusted to the subject.",
            "avoid_confidence_score": True,
            "avoid_backend_language": True,
            "avoid_gpt_language": True,
            "include_additional_notes_provided": True,
            "range_confidence_rule": "Use supplied comp-adjustment math as the factual valuation base. Do not invent a different range. Do not blindly defend it; classify support as CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED.",
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
