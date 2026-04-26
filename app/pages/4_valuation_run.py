import streamlit as st

from app.agent.controller import run_valuation
from core.gpt_client import run_gpt_report
from core.reporting.docx_exporter import report_markdown_to_docx_bytes
from core.reporting.report_payload_builder import build_report_payload

st.set_page_config(page_title="ICHIBAN - Valuation Run", page_icon="📈", layout="wide")

st.title("Module 4 — Valuation Run")

subject_profile = st.session_state.get("subject_profile", {})
market_file = st.session_state.get("market_file")
market_inspection = st.session_state.get("market_inspection", {})

subject_ready = subject_profile.get("subject_profile_ready", False)
market_ready = market_file is not None

c1, c2 = st.columns(2)
c1.write(f"Subject ready: {subject_ready}")
c2.write(f"Market data ready: {market_ready}")

if market_inspection:
    with st.expander("Current market-data handoff summary", expanded=False):
        st.json(market_inspection)

if subject_ready and market_ready:
    st.success("Running valuation engine...")

    results = run_valuation(market_file, subject_profile)
    st.session_state["valuation_results"] = results

    st.subheader("Valuation Engine Status")
    st.write(
        {
            "rows_loaded": results.get("rows_loaded"),
            "closed_rows": results.get("closed_rows"),
            "closed_rows_in_subject_size_band": results.get("closed_rows_in_subject_size_band"),
            "detected_header_row": results.get("detected_header_row"),
            "header_score": results.get("header_score"),
        }
    )

    if results.get("closed_rows_in_subject_size_band", 0) == 0:
        st.warning(
            "No closed rows landed inside the current subject size band. "
            "This means comp filtering is not ready for final pricing yet."
        )

    with st.expander("Engine Debug / Full Output", expanded=False):
        st.json(results)

    st.divider()
    st.subheader("Generate ICHIBAN Insight Report")

    estimated_days_until_market = st.number_input(
        "Estimated days until market",
        min_value=0,
        max_value=365,
        value=30,
        step=1,
        help="Used for the comp disclosure rule. Detailed comps should be included only when listing is expected within 30 days.",
    )

    agent_notes = st.text_area(
        "Agent notes for the final report",
        value="",
        placeholder="Add condition notes, special features, seller timing, pricing concerns, or anything GPT should consider in the narrative.",
    )

    if st.button("Generate Deep-Dive ICHIBAN Report"):
        report_payload = build_report_payload(
            engine_output=results,
            subject_profile=subject_profile,
            market_inspection=market_inspection,
            user_notes=agent_notes,
            estimated_days_until_market=int(estimated_days_until_market),
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

    with st.expander("Generated GPT Report Payload", expanded=False):
        st.json(st.session_state.get("ichiban_report_payload", {}))
else:
    st.warning("Complete previous steps before running valuation.")
