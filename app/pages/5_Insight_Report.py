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

from core.gpt_client import run_gpt_report
from core.gpt_prompt_builder import build_ichiban_report_prompt
from core.reporting.docx_exporter import report_markdown_to_docx_bytes
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

st.title("Module 5 — ICHIBAN Insight Report")
st.subheader("Build the report package and generate the seller-facing report")


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


def _pricing_signature(pricing: Dict[str, Any]) -> Dict[str, str]:
    pricing = pricing or {}
    return {
        "low": _fmt_money(pricing.get("recommended_price_range_low")),
        "high": _fmt_money(pricing.get("recommended_price_range_high")),
        "target": _fmt_money(pricing.get("recommended_list_price")),
    }


def _clean_generated_report_text(report_text: str, pricing: Dict[str, Any]) -> str:
    """Lightly sanitize generated text so seller-facing output stays deliverable-ready."""
    if not report_text:
        return report_text

    cleaned = report_text
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
        kept.append(line)
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


def _build_auto_report_input() -> Dict[str, Any]:
    if not engine_ready:
        return {}
    return build_report_input(
        valuation_engine_result=valuation_engine_result,
        valuation_input_package=valuation_input_package,
        manual_pricing={"manual_price_override": False},
        realtor_notes="",
        buyer_consideration_notes="",
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
        "Existing report_input.json was created by an older report builder. Build / Refresh Report Input before generating or downloading the report."
    )

with st.expander("Locked ICHIBAN seller-facing report standard", expanded=False):
    st.markdown(
        """
1. Recommended Range + Ruler
2. Executive Summary bullets
3. Comparable Evidence table
4. How the Value Was Determined / Generalized Adjustments
5. AVM / Online Benchmarks
6. Current Competition Check
7. Market Momentum
8. Buyer Considerations
9. Strategy / Launch Notes
10. Disclaimer

Ruler labels: **Market Support | Lower Entry | Target Position | Strategic Upper | High-Risk Stretch**.

The high-end marker is not “Market Opportunity.” It is a caution zone unless updates, low inventory, superior features, or early buyer response support it.
"""
    )


# ---------------------------------------------------------------------
# Realtor / seller-facing context controls
# ---------------------------------------------------------------------

st.markdown("## Report Context")
st.caption("These fields do not change valuation math. They help shape the final report in Realtor/Seller language.")

with st.form("report_context_form"):
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

    seller_goal = st.text_area(
        "Seller goal / pricing conversation notes",
        value=existing_pricing.get("seller_goal") or "",
        placeholder="Example: Seller wants to move quickly but does not want to undersell. Needs guidance on whether paint/kitchen work is worth it.",
        height=90,
    )

    realtor_notes = st.text_area(
        "Realtor property notes",
        value=existing_report_input.get("realtor_notes") or "",
        placeholder="Paste walkthrough notes, condition notes, special features, finish quality, layout notes, HOA/gated-community notes, etc.",
        height=160,
    )

    buyer_consideration_notes = st.text_area(
        "Buyer Considerations notes",
        value=existing_report_input.get("buyer_consideration_notes") or "",
        placeholder="Example: Interior paint may affect showing response; kitchen counters/cabinets may be dated; roof is newer; furnace is original; verify condition in field.",
        height=130,
    )

    report_mode = st.selectbox(
        "Report mode",
        options=["seller_friendly_concise", "agent_deep_dive", "field_review"],
        index=0,
        help="Use seller_friendly_concise for the Boca-style baseline report.",
    )

    submitted = st.form_submit_button("Build / Refresh Report Input", type="primary")


manual_pricing: Dict[str, Any] = {
    "manual_price_override": bool(use_manual_pricing_override),
    "pricing_strategy_posture": pricing_strategy_posture,
    "estimated_days_until_market": estimated_days_until_market,
    "seller_goal": seller_goal,
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
        realtor_notes=realtor_notes,
        buyer_consideration_notes=buyer_consideration_notes,
    )
    st.session_state["ichiban_report_input"] = report_input
    st.session_state.pop("ichiban_report_text", None)
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
        realtor_notes=realtor_notes,
        buyer_consideration_notes=buyer_consideration_notes,
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

    prompt = build_ichiban_report_prompt(report_input, report_mode=report_mode)
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

    if st.button("Generate ICHIBAN Insight Report", type="primary", disabled=not api_key_present):
        with st.spinner("Generating ICHIBAN Insight Report..."):
            try:
                report_text = run_gpt_report(prompt)
                report_text = _clean_generated_report_text(report_text, active_pricing)
                st.session_state["ichiban_report_text"] = report_text
                report_path = save_json_file(
                    REPO_ROOT / "data" / "last_gpt_report_metadata.json",
                    {
                        "report_generated": True,
                        "report_mode": report_mode,
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
            docx_bytes = report_markdown_to_docx_bytes(
                report_text,
                title="ICHIBAN INSIGHT - Seller Market Valuation Report",
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
