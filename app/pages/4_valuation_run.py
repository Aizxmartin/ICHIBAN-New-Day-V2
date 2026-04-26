import sys
from pathlib import Path
from dataclasses import asdict, is_dataclass

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.controller import run_valuation

st.set_page_config(page_title="ICHIBAN - Valuation Run", page_icon="📈", layout="wide")

st.title("Module 4 — Valuation Run")
st.subheader("Run the valuation engine using the locked subject profile and normalized MLS data")

subject_profile = st.session_state.get("subject_profile", {})
market_df = st.session_state.get("market_data_normalized")

subject_ready = bool(subject_profile.get("subject_profile_ready"))
market_ready = market_df is not None

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

c1, c2 = st.columns(2)
c1.metric("Subject ready", "True" if subject_ready else "False")
c2.metric("Market data ready", "True" if market_ready else "False")

if not subject_ready:
    st.warning("Subject profile is not ready. Complete Module 2 first.")

if not market_ready:
    st.warning("Market data is not ready. Complete Module 3 first.")

if subject_ready and market_ready:
    with st.spinner("Running valuation engine..."):
        results = run_valuation(market_df, subject_profile)

    if is_dataclass(results):
        results = asdict(results)

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
            st.markdown(f"### Recommended Range: {money_value(low_range)} – {money_value(high_range)}")

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

        with st.expander("Engine Debug / Status Check", expanded=True):
            st.json(results.get("debug", {}))

        with st.expander("Full engine output"):
            safe_results = {}
            for k, v in results.items():
                if isinstance(v, pd.DataFrame):
                    safe_results[k] = f"DataFrame with {len(v)} rows and {len(v.columns)} columns"
                else:
                    safe_results[k] = v
            st.json(safe_results)
