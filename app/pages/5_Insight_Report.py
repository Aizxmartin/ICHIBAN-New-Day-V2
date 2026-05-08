from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.gpt_client import run_gpt_report
from core.gpt_prompt_builder import build_ichiban_report_prompt
from core.report_input_builder import (
    DEFAULT_REPORT_INPUT_PATH,
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
# Realtor / seller-facing context controls
# ---------------------------------------------------------------------

st.markdown("## Report Context")
st.caption("These fields do not change valuation math. They help shape the final report in Realtor/Seller language.")

with st.form("report_context_form"):
    col_a, col_b, col_c = st.columns(3)

    recommended_low = col_a.text_input(
        "Recommended range low",
        value=str(existing_report_input.get("pricing_reconciliation", {}).get("recommended_price_range_low") or ""),
        placeholder="$725,000",
    )
    recommended_high = col_b.text_input(
        "Recommended range high",
        value=str(existing_report_input.get("pricing_reconciliation", {}).get("recommended_price_range_high") or ""),
        placeholder="$750,000",
    )
    recommended_price = col_c.text_input(
        "Recommended list posture / price",
        value=str(existing_report_input.get("pricing_reconciliation", {}).get("recommended_list_price") or ""),
        placeholder="$740,000",
    )

    col_d, col_e = st.columns(2)
    pricing_strategy_posture = col_d.selectbox(
        "Pricing posture",
        options=[
            "",
            "Protective / fast-market posture",
            "Market-aligned posture",
            "Strategic upper-range posture",
            "Aspirational / higher-risk posture",
        ],
        index=0,
    )
    estimated_days_until_market = col_e.text_input(
        "Estimated days until market",
        value=str(existing_report_input.get("pricing_reconciliation", {}).get("estimated_days_until_market") or ""),
        placeholder="0, 15, 30, 45...",
    )

    seller_goal = st.text_area(
        "Seller goal / pricing conversation notes",
        value=existing_report_input.get("pricing_reconciliation", {}).get("seller_goal") or "",
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


manual_pricing = {
    "recommended_price_range_low": recommended_low,
    "recommended_price_range_high": recommended_high,
    "recommended_list_price": recommended_price,
    "pricing_strategy_posture": pricing_strategy_posture,
    "estimated_days_until_market": estimated_days_until_market,
    "seller_goal": seller_goal,
}


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
    st.success(f"Report input saved to {saved_path}")
else:
    report_input = st.session_state.get("ichiban_report_input") or existing_report_input

if not report_input and engine_ready:
    report_input, saved_path = build_and_save_report_input(
        valuation_engine_result=valuation_engine_result,
        valuation_input_package=valuation_input_package,
        manual_pricing=manual_pricing,
        realtor_notes=realtor_notes,
        buyer_consideration_notes=buyer_consideration_notes,
    )
    st.session_state["ichiban_report_input"] = report_input
    st.info(f"Initial report input created at {saved_path}")


# ---------------------------------------------------------------------
# Preview and downloads
# ---------------------------------------------------------------------

if report_input:
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

    if st.button("Generate Insight Report", type="primary", disabled=not api_key_present):
        with st.spinner("Generating ICHIBAN Insight Report..."):
            try:
                report_text = run_gpt_report(prompt)
                st.session_state["ichiban_report_text"] = report_text
                report_path = save_json_file(
                    REPO_ROOT / "data" / "last_gpt_report_metadata.json",
                    {
                        "report_generated": True,
                        "report_mode": report_mode,
                        "report_input_path": str(DEFAULT_REPORT_INPUT_PATH),
                    },
                )
                (REPO_ROOT / "data" / "ichiban_insight_report.md").write_text(report_text, encoding="utf-8")
                st.success(f"Report generated. Metadata saved to {report_path}")
            except Exception as exc:
                st.error(f"Insight report generation failed: {exc}")

    report_text = st.session_state.get("ichiban_report_text")
    report_md_path = REPO_ROOT / "data" / "ichiban_insight_report.md"
    if not report_text and report_md_path.exists():
        report_text = report_md_path.read_text(encoding="utf-8")

    if report_text:
        st.markdown("## ICHIBAN Insight Report Preview")
        st.markdown(report_text)
        st.download_button(
            label="Download report markdown",
            data=report_text,
            file_name="ichiban_insight_report.md",
            mime="text/markdown",
        )
else:
    st.info("Build the report input after Module 4 has produced valuation engine output.")
