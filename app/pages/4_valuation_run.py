import streamlit as st
from app.agent.controller import run_valuation

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

    st.subheader("Engine Output")
    st.json(results)

    if results.get("closed_rows_in_subject_size_band", 0) == 0:
        st.warning("No closed rows landed inside the current subject size band. This means comp filtering is not ready for final pricing yet.")
else:
    st.warning("Complete previous steps before running valuation.")
