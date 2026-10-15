from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ui_theme import apply_ichiban_theme, ichiban_hero

from core.gpt_client import run_gpt_report
from core.gpt_prompt_builder import build_ichiban_report_prompt
from core.reporting.docx_exporter import report_markdown_to_docx_bytes
from core.reporting.report_quality import validate_tarzan_report
from core.report_routing import DEFAULT_REPORT_VERSION, REPORT_VERSIONS
from core.report_input_builder import (
    CURRENT_REPORT_INPUT_VERSION,
    DEFAULT_REPORT_INPUT_PATH,
    build_report_input,
    build_and_save_report_input,
    json_safe,
    load_json_file,
    save_json_file,
)


st.set_page_config(
    page_title="ICHIBAN - Insight Report",
    page_icon="🧭",
    layout="wide",
)

apply_ichiban_theme()


st.title("Module 5 — ICHIBAN Insight Report")
st.subheader("Build the report package and generate the Tarzan valuation analysis")

STANDARD_REPORT_NAME = "Tarzan Valuation Analysis"
DEFAULT_REPORT_TYPE = STANDARD_REPORT_NAME

REPORT_LANGUAGE_RULE = (
    "The value range is based on closed comparable evidence. The market momentum section reviews a broader "
    "competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction."
)

REPORT_CONTEXT_PATH = REPO_ROOT / "data" / "report_context.json"



# ---------------------------------------------------------------------
# Load existing handoffs
# ---------------------------------------------------------------------

valuation_engine_result: Dict[str, Any] = (
    st.session_state.get("valuation_engine_result")
    or load_json_file(REPO_ROOT / "data" / "valuation_engine_output.json")
)
valuation_input_package: Dict[str, Any] = load_json_file(REPO_ROOT / "data" / "valuation_input_package.json")
existing_report_input: Dict[str, Any] = load_json_file(DEFAULT_REPORT_INPUT_PATH)
existing_report_metadata: Dict[str, Any] = load_json_file(REPO_ROOT / "data" / "last_gpt_report_metadata.json")
existing_report_context: Dict[str, Any] = load_json_file(REPORT_CONTEXT_PATH)

engine_ready = bool(valuation_engine_result)
input_package_ready = bool(valuation_input_package)
report_input_ready = bool(existing_report_input)

c1, c2, c3 = st.columns(3)
c1.metric("Valuation engine output", str(engine_ready))
c2.metric("Valuation input package", str(input_package_ready))
c3.metric("Existing report input", str(report_input_ready))

if not engine_ready:
    st.warning("No valuation engine output found yet. Run Module 4 first, then return to this page.")

if engine_ready and not input_package_ready:
    st.info("The report can still be built from valuation engine output, but saving the Module 4 valuation input package is recommended.")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _fmt_money(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"${float(str(value).replace('$', '').replace(',', '').strip()):,.0f}"
    except Exception:
        return str(value)


def _first_session_dataframe(*keys: str) -> Any:
    """Return the first dataframe-like object from session_state without boolean-testing a DataFrame."""
    for key in keys:
        value = st.session_state.get(key)
        if value is not None:
            return value
    return None


def _current_subject_display() -> str:
    subject = (valuation_engine_result or {}).get("subject_summary") or (valuation_input_package or {}).get("subject_profile") or {}
    return str(
        subject.get("subject_address")
        or subject.get("address")
        or subject.get("full_address")
        or ""
    ).strip()


def _context_subject_mismatch(context: Dict[str, Any]) -> bool:
    saved_subject = str((context or {}).get("subject_address") or "").strip().lower()
    current_subject = _current_subject_display().lower()
    return bool(saved_subject and current_subject and saved_subject != current_subject)


def _clear_report_context_state() -> None:
    for key in [
        "report_notes_for_gpt",
        "realtor_notes_for_gpt",
        "buyer_consideration_notes_for_gpt",
        "upgrade_notes_for_gpt",
        "showing_feedback_notes_for_gpt",
        "listing_history_notes_for_gpt",
        "seller_goal_for_gpt",
        "after_active_current_list_price_for_gpt",
    ]:
        st.session_state.pop(key, None)
    st.session_state.pop("ichiban_report_input", None)
    st.session_state.pop("ichiban_report_text", None)
    st.session_state.pop("ichiban_report_prompt", None)
    for path in [REPORT_CONTEXT_PATH, DEFAULT_REPORT_INPUT_PATH, REPO_ROOT / "data" / "ichiban_insight_report.md"]:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


def _pricing_signature(pricing: Dict[str, Any]) -> Dict[str, str]:
    pricing = pricing or {}
    return {
        "low": _fmt_money(pricing.get("recommended_price_range_low")),
        "high": _fmt_money(pricing.get("recommended_price_range_high")),
        "target": _fmt_money(pricing.get("recommended_list_price")),
    }


def _sanitize_seller_facing_text(text: str) -> str:
    """Translate backend/engine wording into seller-facing language."""
    replacements = [
        (r"(?i)\bengine 1004MC inputs\b", "market-pattern inputs"),
        (r"(?i)\bengine's seller calculation\b", "seller-facing momentum review"),
        (r"(?i)\bengine’s seller calculation\b", "seller-facing momentum review"),
        (r"(?i)\bclassified as ([\"'][^\"']+[\"']) by the engine\b", r"supports a \1 market reading"),
        (r"(?i)\bclassified as ([^.;,]+) by the engine\b", r"supports a \1 market reading"),
        (r"(?i)\bthe engine applied\b", "the analysis considered"),
        (r"(?i)\bengine applied\b", "the analysis considered"),
        (r"(?i)\bthe engine found\b", "the analysis indicates"),
        (r"(?i)\bengine found\b", "the analysis indicates"),
        (r"(?i)\bthe engine used\b", "the analysis used"),
        (r"(?i)\bengine used\b", "the analysis used"),
        (r"(?i)\bthe engine preserved\b", "the analysis retained"),
        (r"(?i)\bnet_price\s*=\s*close_price\s*-\s*concessions\b", "net price reflects closed price less any reported concessions"),
        (r"(?i)\btime_adjustment\s*=\s*0\b", "no material time adjustment was applied"),
        (r"(?i)\bengine output\b", "adjusted analysis"),
        (r"(?i)\bthe engine's\b", "the analysis"),
        (r"(?i)\bthe engine’s\b", "the analysis"),
        (r"(?i)\bengine's\b", "analysis"),
        (r"(?i)\bengine’s\b", "analysis"),
        (r"(?i)\bby the engine\b", "by the analysis"),
        (r"(?i)\bengine\b", "analysis"),
        (r"(?i)Recommended Range \+ Ruler", "Recommended Range"),
    ]
    cleaned = text or ""
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned


def _line_contains_confusing_momentum_metric(line: str) -> bool:
    normalized = (line or "").lower()
    blocked_phrases = [
        "estimated 30-day success rate",
        "seller competition months",
        "months_of_seller_competition",
        "success rate high",
        "practical seller competition months",
    ]
    return any(phrase in normalized for phrase in blocked_phrases)


def _clean_generated_report_text(report_text: str, pricing: Dict[str, Any]) -> str:
    """Lightly sanitize generated text so seller-facing output stays deliverable-ready."""
    if not report_text:
        return report_text

    cleaned = _sanitize_seller_facing_text(report_text)
    cleaned = re.sub(r"(?i)\bmarket opportunity\b", "High-Risk Stretch", cleaned)
    cleaned = re.sub(r"(?i)\breconciliation\b", "pricing basis", cleaned)

    # Remove unfinished assistant-style offers and Final note blocks.
    lines = cleaned.splitlines()
    kept = []
    skip_final_note = False
    for line in lines:
        stripped = line.strip()
        normalized = stripped.lower().strip("# ")
        if normalized.startswith("final note"):
            skip_final_note = True
            continue
        if skip_final_note:
            if stripped.startswith("#"):
                skip_final_note = False
            else:
                continue
        if "if you want, i can" in stripped.lower():
            continue
        if _line_contains_confusing_momentum_metric(stripped):
            continue
        kept.append(_sanitize_seller_facing_text(line))
    cleaned = "\n".join(kept).strip()

    low = _fmt_money(pricing.get("recommended_price_range_low"))
    high = _fmt_money(pricing.get("recommended_price_range_high"))
    target = _fmt_money(pricing.get("recommended_list_price"))

    if low and high:
        desired = f"{low} — {high}"
        patterns = [
            r"(?i)(Recommended list price range[^:\n]*:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
            r"(?i)(Recommended Market Entry Range[^:\n]*:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
            r"(?i)(Final suggested list range:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
            r"(?i)(Suggested list:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
            r"(?i)(Suggested list range:\s*)\$[0-9,]+\s*[—-]\s*\$[0-9,]+",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, rf"\1{desired}", cleaned)
        cleaned = re.sub(
            r"(?i)(Suggested list:\s*Price above\s*)\$[0-9,]+",
            rf"\1{high}",
            cleaned,
        )
        cleaned = re.sub(
            r"(?i)(Price above\s*)\$[0-9,]+",
            rf"\1{high}",
            cleaned,
        )

    if target:
        cleaned = re.sub(
            r"(?i)(Recommended strategic list price[^:\n]*:\s*)\$?[0-9,—\-\s]*",
            rf"\1{target}",
            cleaned,
        )
        cleaned = cleaned.replace("Recommended strategic list price: —", f"Recommended strategic list price: {target}")

    return cleaned


def _report_input_is_current(report_input: Dict[str, Any]) -> bool:
    return bool(report_input) and report_input.get("report_input_version") == CURRENT_REPORT_INPUT_VERSION


def _saved_markdown_matches_current(report_input: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    if not report_input or not metadata:
        return False
    if metadata.get("report_input_version") != CURRENT_REPORT_INPUT_VERSION:
        return False
    expected = _pricing_signature(report_input.get("pricing_reconciliation", {}))
    saved = metadata.get("pricing_signature") or {}
    return expected == saved


def _report_has_realtor_context(report_input: Dict[str, Any]) -> bool:
    """True when the final GPT prompt will receive actual Realtor/market notes."""
    if not report_input:
        return False
    direct_fields = [
        report_input.get("report_notes"),
        report_input.get("realtor_notes"),
    ]
    additional = report_input.get("additional_notes_provided") or {}
    categories = additional.get("categories") if isinstance(additional, dict) else []
    category_notes = []
    if isinstance(categories, list):
        category_notes = [item.get("notes") for item in categories if isinstance(item, dict)]
    review = report_input.get("pre_gpt_realtor_notes_review") or {}
    review_flags = [
        review.get("report_notes_supplied"),
        review.get("realtor_notes_supplied"),
    ]
    return any(str(item or "").strip() for item in direct_fields + category_notes) or any(bool(flag) for flag in review_flags)


def _build_auto_report_input() -> Dict[str, Any]:
    if not engine_ready:
        return {}
    return build_report_input(
        valuation_engine_result=valuation_engine_result,
        valuation_input_package=valuation_input_package,
        manual_pricing={"manual_price_override": False},
        realtor_notes=st.session_state.get("report_notes_for_gpt") or existing_report_input.get("report_notes") or existing_report_input.get("realtor_notes") or "",
        buyer_consideration_notes="",
        additional_context={
            "report_type": st.session_state.get("report_type_selection", DEFAULT_REPORT_TYPE),
            "report_version": DEFAULT_REPORT_VERSION,
            "input_mode": "hybrid",
            "market_df_for_routing": _first_session_dataframe(
                "competition_market_data_normalized",
                "momentum_file_df",
                "valuation_comp_data_normalized",
                "valuation_file_df",
                "market_data_normalized",
            ),
            "field_intelligence_notes": st.session_state.get("report_notes_for_gpt") or "",
            "report_language_rule": REPORT_LANGUAGE_RULE,
        },
    )


# ---------------------------------------------------------------------
# Locked report standard — no competing report names
# ---------------------------------------------------------------------

report_type = STANDARD_REPORT_NAME
report_mode = DEFAULT_REPORT_VERSION
st.session_state["report_type_selection"] = STANDARD_REPORT_NAME

st.markdown("## Report Standard")
st.success("Tarzan Valuation Analysis is locked as the standard ICHIBAN output.")
st.caption(
    "Tarzan Valuation Analysis is the active report branch. BBC seller interpretation and Retrospect tactical review are paused until the objective valuation branch is stable. Realtor notes are field intelligence inside Tarzan when supplied."
)

# ---------------------------------------------------------------------
# Current auto report input and stale-input handling
# ---------------------------------------------------------------------

auto_report_input: Dict[str, Any] = _build_auto_report_input()
auto_pricing: Dict[str, Any] = auto_report_input.get("pricing_reconciliation", {}) if auto_report_input else {}
existing_is_current = _report_input_is_current(existing_report_input)
existing_pricing: Dict[str, Any] = existing_report_input.get("pricing_reconciliation", {}) if existing_report_input else {}

# Manual pricing is honored only if a current report_input explicitly says it was a manual override.
existing_is_manual_current = (
    existing_is_current
    and existing_pricing.get("source") == "manual_user_entry"
    and bool(existing_pricing.get("manual_price_override"))
)
default_pricing: Dict[str, Any] = existing_pricing if existing_is_manual_current else auto_pricing

if existing_report_input and not existing_is_current:
    st.warning(
        "Existing report_input.json was created by an older report builder. Build / Refresh Tarzan Report Input before generating or downloading the report."
    )

with st.expander("Current Tarzan valuation report standards", expanded=False):
    st.markdown(
        """
**Current Tarzan-only report standard**

1. Tarzan Valuation Analysis is the only active report output in this branch.
2. The range snapshot may appear at the top, but it is evidence context, not a seller circle sheet.
3. Agent Review Inputs and BBC Seller Point boxes are paused.
4. The report must explain comp selection, appraisal-style adjustments, adjusted comp evidence, range reconciliation, market momentum, absorption, concessions/net behavior, 1004MC/time review, price sensitivity, data verification, and final status.
5. The final status must be CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED.
6. Realtor notes are field intelligence when supplied; they do not silently rewrite comp math.
7. Report Date appears near the top and the recommendation is based on information available as of that date.

**Range confidence rule**

Once ICHIBAN selects the Recommended Range, the report explains why that range is reasonable. It does not argue higher or lower unless the selected range changes.

**Caveat rule**

Caveats must be material and report-specific. No casual filler caveats.
"""
    )


# ---------------------------------------------------------------------
# Realtor / seller-facing context controls
# ---------------------------------------------------------------------

st.markdown("## Report Context")
st.caption("One pre-appointment notes field. These notes do not rewrite valuation math; they give Tarzan field intelligence or verification context when supplied.")
st.info(
    "For the first-run Tarzan valuation branch, use one notes field only. Add concise pre-appointment facts learned from the seller, visit, photos, condition review, or known marketability issues. Larger after-active/showing-history review belongs in ICHIBAN Retrospect later."
)

with st.form("report_context_form"):
    report_date = st.text_input(
        "Report date",
        value=str(existing_report_input.get("report_date") or ""),
        placeholder="YYYY-MM-DD; leave blank to use today's date",
        help="The report recommendation is based on information available as of this date.",
    )

    use_manual_pricing_override = st.checkbox(
        "Manually override the auto-drafted recommended range",
        value=existing_is_manual_current,
        help=(
            "Leave unchecked to use the current engine-derived ICHIBAN range. "
            "Check only when the Realtor intentionally wants to override the recommended range."
        ),
    )

    col_a, col_b, col_c = st.columns(3)

    recommended_low = col_a.text_input(
        "Recommended range low",
        value=_fmt_money(default_pricing.get("recommended_price_range_low")),
        placeholder="$660,000",
        disabled=not use_manual_pricing_override,
    )
    recommended_high = col_b.text_input(
        "Recommended range high",
        value=_fmt_money(default_pricing.get("recommended_price_range_high")),
        placeholder="$675,000",
        disabled=not use_manual_pricing_override,
    )
    recommended_price = col_c.text_input(
        "Recommended list posture / price",
        value=_fmt_money(default_pricing.get("recommended_list_price")),
        placeholder="$665,000",
        disabled=not use_manual_pricing_override,
    )

    col_d, col_e = st.columns(2)
    posture_options = [
        "",
        "Protective / fast-market posture",
        "Evidence-aligned / recommended posture",
        "Strategic upper-range posture",
        "High-risk stretch posture",
    ]
    saved_posture = str(existing_pricing.get("pricing_strategy_posture") or auto_pricing.get("pricing_strategy_posture") or "")
    posture_index = posture_options.index(saved_posture) if saved_posture in posture_options else 0
    pricing_strategy_posture = col_d.selectbox(
        "Pricing posture",
        options=posture_options,
        index=posture_index,
    )
    estimated_days_until_market = col_e.text_input(
        "Estimated days until market",
        value=str(existing_pricing.get("estimated_days_until_market") or ""),
        placeholder="0, 15, 30, 45...",
    )

    context_values = existing_report_context.get("values") if isinstance(existing_report_context.get("values"), dict) else {}
    if _context_subject_mismatch(existing_report_context):
        st.warning("Saved Report Context appears to belong to a different subject. Clear it or save new context for the current subject before generating a report.")

    report_notes = st.text_area(
        "Report Notes / Field Intelligence for Tarzan",
        value=(
            st.session_state.get("report_notes_for_gpt")
            or context_values.get("report_notes")
            or context_values.get("realtor_notes")
            or existing_report_input.get("report_notes")
            or existing_report_input.get("realtor_notes")
            or ""
        ),
        placeholder=(
            "Optional pre-appointment notes only. Example: seller says smoke odor may be present; no fenced yard; "
            "recent paint completed; seller wants to move soon; verify condition against remodeled comps. "
            "Do not paste a full after-active/showing log here — save that for Retrospect later."
        ),
        height=220,
        help="Passed into Tarzan as field intelligence/verification context. It does not silently change the comp math.",
        key="report_notes_for_gpt",
    )

    st.info(
        "Report version is locked: Tarzan Valuation Analysis. "
        "BBC and Retrospect are paused. Manual pricing/input choices do not change the current Tarzan-only report standard."
    )

    b1, b2, b3 = st.columns(3)
    save_context = b1.form_submit_button("Save Context As-Is")
    clear_context = b2.form_submit_button("Clear Report Context")
    submitted = b3.form_submit_button("Build / Refresh Tarzan Report Input", type="primary")


if clear_context:
    _clear_report_context_state()
    st.success("Report Context cleared for the current workspace.")
    st.rerun()

if save_context:
    context_payload = {
        "subject_address": _current_subject_display(),
        "context_source": "module_5_report_context",
        "current_context_controls": True,
        "values": {
            "report_notes": report_notes,
        },
    }
    save_json_file(REPORT_CONTEXT_PATH, context_payload)
    st.success("Report Context saved as current for this subject.")
    st.rerun()


manual_pricing: Dict[str, Any] = {
    "manual_price_override": bool(use_manual_pricing_override),
    "pricing_strategy_posture": pricing_strategy_posture,
    "estimated_days_until_market": estimated_days_until_market,
    "report_date": report_date,
    "report_notes": report_notes,
    "realtor_notes": report_notes,
}

if use_manual_pricing_override:
    manual_pricing.update(
        {
            "recommended_price_range_low": recommended_low,
            "recommended_price_range_high": recommended_high,
            "recommended_list_price": recommended_price,
        }
    )


# ---------------------------------------------------------------------
# Build report input
# ---------------------------------------------------------------------

if submitted:
    report_input, saved_path = build_and_save_report_input(
        valuation_engine_result=valuation_engine_result,
        valuation_input_package=valuation_input_package,
        manual_pricing=manual_pricing,
        realtor_notes=report_notes,
        buyer_consideration_notes="",
        additional_context={
            "report_type": report_type,
            "report_mode": DEFAULT_REPORT_VERSION,
            "report_version": DEFAULT_REPORT_VERSION,
            "input_mode": "manual" if use_manual_pricing_override else "hybrid",
            "report_date": report_date,
            "field_intelligence_notes": report_notes,
            "market_df_for_routing": _first_session_dataframe(
                "competition_market_data_normalized",
                "momentum_file_df",
                "valuation_comp_data_normalized",
                "valuation_file_df",
                "market_data_normalized",
            ),
            "report_language_rule": REPORT_LANGUAGE_RULE,
        },
    )
    st.session_state["ichiban_report_input"] = report_input
    st.session_state.pop("ichiban_report_text", None)
    if not _report_has_realtor_context(report_input):
        st.warning("Report input saved, but no Realtor Notes were supplied. The Tarzan GPT valuation report may miss field judgment and active-market context.")
    else:
        st.success(f"Report input saved to {saved_path}")
    st.caption(
        "Current recommended range: "
        f"{_fmt_money(report_input.get('pricing_reconciliation', {}).get('recommended_price_range_low'))} - "
        f"{_fmt_money(report_input.get('pricing_reconciliation', {}).get('recommended_price_range_high'))}; "
        f"Target: {_fmt_money(report_input.get('pricing_reconciliation', {}).get('recommended_list_price'))}"
    )
else:
    session_report_input = st.session_state.get("ichiban_report_input")
    if _report_input_is_current(session_report_input or {}):
        report_input = session_report_input
    elif existing_is_current and existing_is_manual_current:
        report_input = existing_report_input
    else:
        report_input = auto_report_input

if not report_input and engine_ready:
    report_input, saved_path = build_and_save_report_input(
        valuation_engine_result=valuation_engine_result,
        valuation_input_package=valuation_input_package,
        manual_pricing=manual_pricing,
        realtor_notes=report_notes,
        buyer_consideration_notes="",
        additional_context={
            "report_type": report_type,
            "report_mode": DEFAULT_REPORT_VERSION,
            "report_version": DEFAULT_REPORT_VERSION,
            "input_mode": "manual" if use_manual_pricing_override else "hybrid",
            "report_date": report_date,
            "field_intelligence_notes": report_notes,
            "market_df_for_routing": _first_session_dataframe(
                "competition_market_data_normalized",
                "momentum_file_df",
                "valuation_comp_data_normalized",
                "valuation_file_df",
                "market_data_normalized",
            ),
            "report_language_rule": REPORT_LANGUAGE_RULE,
        },
    )
    st.session_state["ichiban_report_input"] = report_input
    st.session_state.pop("ichiban_report_text", None)
    st.info(f"Initial report input created at {saved_path}")


# ---------------------------------------------------------------------
# Preview and downloads
# ---------------------------------------------------------------------

if report_input:
    active_pricing = report_input.get("pricing_reconciliation", {})
    active_signature = _pricing_signature(active_pricing)

    st.markdown("## Active Report Pricing")
    p1, p2, p3 = st.columns(3)
    p1.metric("Range Low", active_signature["low"] or "—")
    p2.metric("Target", active_signature["target"] or "—")
    p3.metric("Range High", active_signature["high"] or "—")

    routing = report_input.get("report_routing") or (report_input.get("report_package") or {}).get("report_routing") or {}
    with st.expander("Ichiban Report Routing Diagnostic", expanded=bool(routing.get("after_active_overlay"))):
        if routing:
            st.json(json_safe(routing))
            if routing.get("after_active_overlay"):
                st.warning(
                    "Active/current market context is detected. In Tarzan-first mode it is context only, not a separate Retrospect tactical recommendation."
                )
            elif routing.get("market_file_summary", {}).get("competition_file_inferred_from_same_file"):
                st.info("Same-file competition support detected from the MLS file.")
        else:
            st.caption("No routing diagnostic found yet. Build / Refresh Tarzan Report Input to regenerate v14 routing.")

    st.markdown("## Report Input Preview")
    with st.expander("View report_input.json", expanded=False):
        st.json(json_safe(report_input))

    report_input_json = json.dumps(json_safe(report_input), indent=2, ensure_ascii=False)
    st.download_button(
        label="Download report_input.json",
        data=report_input_json,
        file_name="report_input.json",
        mime="application/json",
    )

    resolved_report_mode = DEFAULT_REPORT_VERSION
    prompt = build_ichiban_report_prompt(report_input, report_mode=resolved_report_mode)
    st.session_state["ichiban_report_prompt"] = prompt

    with st.expander("Preview report prompt", expanded=False):
        st.code(prompt)

    st.download_button(
        label="Download report prompt preview",
        data=prompt,
        file_name="ichiban_report_prompt_preview.txt",
        mime="text/plain",
    )

    st.divider()
    st.markdown("## Generate Report")

    api_key_present = bool(os.getenv("OPENAI_API_KEY"))
    if not api_key_present:
        st.info(
            "OPENAI_API_KEY is not set, so this page will build the report input and prompt preview but will not generate the report yet. "
            "Set the key locally when you are ready to test live report generation."
        )

    notes_present_for_gpt = _report_has_realtor_context(report_input)
    after_active_overlay = False  # Retrospect / Current Market Context tactical branch is paused in v20.5
    proceed_without_notes = False

    if not notes_present_for_gpt:
        st.warning(
            "No Realtor Notes or Listing History notes are present in the current report input. Before running GPT, add notes above and click Build / Refresh Tarzan Report Input, or explicitly proceed without notes."
        )
        proceed_without_notes = st.checkbox(
            "Proceed without Realtor Notes for this run (not recommended)",
            value=False,
            help="Use only when there truly are no field notes, showing feedback, seller goals, or active-market observations to add.",
        )

    if after_active_overlay and not notes_present_for_gpt and not proceed_without_notes:
        st.error(
            "Current market/field context is detected, but Realtor Notes are blank. Add field notes if they are material, or proceed without notes."
        )

    generate_disabled = (not api_key_present) or (after_active_overlay and not notes_present_for_gpt and not proceed_without_notes)

    if st.button("Generate Tarzan Valuation Analysis", type="primary", disabled=generate_disabled):
        with st.spinner("Generating Tarzan Valuation Analysis..."):
            try:
                report_text = run_gpt_report(prompt)
                report_text = _clean_generated_report_text(report_text, active_pricing)
                quality = validate_tarzan_report(report_text)
                if not quality.passed:
                    st.error("Tarzan quality gate failed. The report was not saved because required valuation sections are missing or paused report language leaked in.")
                    for item in quality.errors:
                        st.error(item)
                else:
                    for item in quality.warnings:
                        st.warning(item)
                    st.session_state["ichiban_report_text"] = report_text
                    report_path = save_json_file(
                        REPO_ROOT / "data" / "last_gpt_report_metadata.json",
                        {
                            "report_generated": True,
                            "report_mode": DEFAULT_REPORT_VERSION,
                            "report_input_path": str(DEFAULT_REPORT_INPUT_PATH),
                            "report_input_version": CURRENT_REPORT_INPUT_VERSION,
                            "pricing_signature": active_signature,
                        },
                    )
                    (REPO_ROOT / "data" / "ichiban_insight_report.md").write_text(report_text, encoding="utf-8")
                    st.success(f"Report generated. Metadata saved to {report_path}")
            except Exception as exc:
                st.error(f"Insight report generation failed: {exc}")

    report_text = st.session_state.get("ichiban_report_text")
    report_md_path = REPO_ROOT / "data" / "ichiban_insight_report.md"
    saved_md_matches = _saved_markdown_matches_current(report_input, existing_report_metadata)

    if not report_text and report_md_path.exists() and saved_md_matches:
        report_text = report_md_path.read_text(encoding="utf-8")
    elif not report_text and report_md_path.exists() and not saved_md_matches:
        st.warning(
            "A saved markdown report exists, but it does not match the current report-input version or pricing values. Generate a fresh report before downloading the DOCX."
        )

    if report_text:
        report_text = _clean_generated_report_text(report_text, active_pricing)
        st.markdown("## ICHIBAN Insight Report Preview")
        st.markdown(report_text)
        st.download_button(
            label="Download report markdown",
            data=report_text,
            file_name="ichiban_insight_report.md",
            mime="text/markdown",
        )

        try:
            quality = validate_tarzan_report(report_text)
            if not quality.passed:
                st.error("DOCX export blocked by Tarzan quality gate.")
                for item in quality.errors:
                    st.error(item)
                st.stop()
            docx_bytes = report_markdown_to_docx_bytes(
                report_text,
                title="ICHIBAN INSIGHT - Tarzan Valuation Analysis",
                report_input=report_input,
            )
            st.download_button(
                label="Download report DOCX",
                data=docx_bytes,
                file_name="ichiban_insight_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as exc:
            st.warning(f"DOCX export is not available yet: {exc}")
else:
    st.info("Build the report input after Module 4 has produced valuation engine output.")
