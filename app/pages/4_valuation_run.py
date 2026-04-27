import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.controller import run_valuation
from core.gpt_client import run_gpt_report
from core.reporting.docx_exporter import report_markdown_to_docx_bytes
from core.reporting.report_payload_builder import build_report_payload

st.set_page_config(page_title="ICHIBAN - Valuation Run", page_icon="📈", layout="wide")

st.title("Module 4 — Valuation Run")
st.subheader("Run the valuation engine using the locked subject profile and normalized MLS data")

subject_profile = st.session_state.get("subject_profile", {})
market_df = st.session_state.get("market_data_normalized")
market_inspection = st.session_state.get("market_inspection", {})
one_hundred_four_mc_summary = st.session_state.get("one_hundred_four_mc_summary", {})

subject_ready = bool(subject_profile.get("subject_profile_ready"))
market_ready = market_df is not None
DEV_DEBUG = os.getenv("ICHIBAN_DEV_DEBUG") == "1"


def count_value(value):
    if isinstance(value, pd.DataFrame):
        return len(value)
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def money_value(value):
    if value is None:
        return "—"
    try:
        return f"${float(value):,.0f}"
    except Exception:
        return "—"


def safe_dataframe(df):
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str)
    return out


def compact_results_for_json(results):
    safe_results = {}
    for k, v in (results or {}).items():
        if isinstance(v, pd.DataFrame):
            safe_results[k] = f"DataFrame with {len(v)} rows and {len(v.columns)} columns"
        else:
            safe_results[k] = v
    return safe_results


# --- Status ---
c1, c2, c3 = st.columns(3)
c1.metric("Subject ready", "True" if subject_ready else "False")
c2.metric("Market data ready", "True" if market_ready else "False")
c3.metric("1004MC supplied", "True" if one_hundred_four_mc_summary.get("is_supplied") else "False")

if market_inspection and DEV_DEBUG:
    with st.expander("Developer: Current market-data handoff summary", expanded=False):
        st.json(market_inspection)

if not subject_ready:
    st.warning("Subject profile is not ready. Complete Module 2 first.")

if not market_ready:
    st.warning("Market data is not ready. Complete Module 3 first.")


# --- Run Engine ---
if subject_ready and market_ready:
    with st.spinner("Running valuation engine..."):
        results = run_valuation(
            market_df,
            subject_profile,
            one_hundred_four_mc_summary=one_hundred_four_mc_summary,
        )

    st.session_state["valuation_results"] = results

    if results.get("error"):
        st.error(results["error"])
    else:
        st.success("Valuation engine completed.")

        st.markdown("## Comp Engine Summary")

        top1, top2, top3, top4 = st.columns(4)
        top1.metric("Closed Rows", count_value(results.get("closed_rows")))
        top2.metric("Priced Closed", count_value(results.get("priced_closed_rows")))
        top3.metric("Candidate Comps", count_value(results.get("candidate_comps")))
        top4.metric("Selected Comps", count_value(results.get("selected_comps")))

        low_range = results.get("recommended_low")
        high_range = results.get("recommended_high")

        if low_range is not None and high_range is not None:
            st.markdown(f"### Evidence Range: {money_value(low_range)} – {money_value(high_range)}")

        avg_ppsf = results.get("average_ppsf")
        median_price = results.get("median_effective_price")

        c5, c6 = st.columns(2)
        c5.metric("Average PPSF", money_value(avg_ppsf))
        c6.metric("Median Effective Price", money_value(median_price))

        selected_preview = results.get("selected_comp_preview")

        if isinstance(selected_preview, pd.DataFrame) and not selected_preview.empty:
            st.markdown("### Selected Comparable Preview")
            st.dataframe(safe_dataframe(selected_preview), width="stretch")
        else:
            st.warning("No selected comp preview was returned.")

        avm_values = []
        for label, key in [("RealAVM", "real_avm"), ("Zillow", "zillow_estimate"), ("Redfin", "redfin_estimate")]:
            value = subject_profile.get(key)
            if value not in (None, "", 0):
                avm_values.append((label, value))

        with st.expander("Pre-API Handoff Checks", expanded=False):
            st.markdown("**Range separation rule:** AVM evidence is secondary support only. Comp evidence remains the primary valuation range.")
            if avm_values:
                st.write("AVM values supplied:")
                for label, value in avm_values:
                    st.write(f"- {label}: {money_value(value)}")
            else:
                st.write("No Zillow/Redfin/RealAVM values were supplied. This is allowed.")

            if one_hundred_four_mc_summary.get("is_supplied"):
                st.write("1004MC / time-trend evidence saved:")
                st.json(one_hundred_four_mc_summary)
            else:
                st.write("No 1004MC evidence supplied. This is allowed; formal time adjustments will be omitted unless later provided/calculated.")

        if DEV_DEBUG:
            with st.expander("Developer: Engine Debug / Full Output", expanded=False):
                st.json(compact_results_for_json(results))

        st.divider()
        st.markdown("## Generate ICHIBAN Insight Report")

        estimated_days_until_market = st.number_input(
            "Estimated days until market",
            min_value=0,
            max_value=365,
            value=int(st.session_state.get("estimated_days_until_market", 30)),
            step=1,
            help="Used for the comp disclosure rule. Detailed comps should be included only when listing is expected within 30 days.",
        )
        st.session_state["estimated_days_until_market"] = int(estimated_days_until_market)

        agent_notes = st.text_area(
            "Agent notes for the final report",
            value=st.session_state.get("agent_notes_for_report", ""),
            placeholder="Add condition notes, special features, seller timing, pricing concerns, or anything GPT should consider in the narrative.",
            height=140,
        )
        st.session_state["agent_notes_for_report"] = agent_notes

        if st.button("Generate Deep-Dive ICHIBAN Report"):
            report_payload = build_report_payload(
                engine_output=results,
                subject_profile=subject_profile,
                market_inspection=market_inspection,
                user_notes=agent_notes,
                estimated_days_until_market=int(estimated_days_until_market),
                one_hundred_four_mc_summary=one_hundred_four_mc_summary,
            )
            st.session_state["ichiban_report_payload"] = report_payload

            with st.spinner("Calling mini GPT with ICHIBAN governance rules..."):
                try:
                    report_text = run_gpt_report(report_payload)
                    st.session_state["ichiban_report_text"] = report_text
                except Exception as exc:
                    st.error(f"GPT report generation failed: {exc}")

        report_text = st.session_state.get("ichiban_report_text")
        if report_text:
            st.markdown("## ICHIBAN Insight Report")
            st.markdown(report_text)

            subject_address = subject_profile.get("subject_address") or "Subject_Property"
            safe_name = "".join(ch if ch.isalnum() else "_" for ch in subject_address).strip("_")
            file_name = f"{safe_name}_ICHIBAN_Insight_Report.docx"

            docx_bytes = report_markdown_to_docx_bytes(
                report_text,
                title=f"ICHIBAN Insight Report — {subject_address}",
            )

            st.download_button(
                label="Download Clean .docx Report",
                data=docx_bytes,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        if DEV_DEBUG:
            with st.expander("Developer: Generated GPT Report Payload", expanded=False):
                st.json(st.session_state.get("ichiban_report_payload", {}))
else:
    st.info("Complete Modules 2 and 3 before running valuation.")
