import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.market_mapping import inspect_market_file

st.set_page_config(page_title="ICHIBAN - Market Data Intake", page_icon="📊", layout="wide")

st.title("Module 3 — Market Data Intake")
st.subheader("Load and inspect the MLS market-data file before valuation")

subject_profile = st.session_state.get("subject_profile", {})
if not subject_profile.get("subject_profile_ready"):
    st.warning("The subject profile is not locked yet. Complete Module 2 before relying on valuation results.")

uploaded_file = st.file_uploader(
    "Upload MLS file (.xlsx, .xls, .csv)",
    type=["xlsx", "xls", "csv"],
    help="Upload the MLS export that will feed comps, status review, and market interpretation.",
)

if uploaded_file is not None:
    st.session_state["market_file"] = uploaded_file

    try:
        inspection = inspect_market_file(uploaded_file)
        st.session_state["market_inspection"] = {
            "detected_header_row": inspection.detected_header_row,
            "header_score": inspection.header_score,
            "matched_fields": inspection.matched_fields,
            "missing_preferred_fields": inspection.missing_preferred_fields,
            "rows_loaded": int(len(inspection.dataframe)),
            "normalized_columns": list(inspection.dataframe.columns),
        }

        st.success("Market file loaded and normalized.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows loaded", int(len(inspection.dataframe)))
        c2.metric("Detected header row", inspection.detected_header_row)
        c3.metric("Header score", inspection.header_score)

        with st.expander("Matched MLS fields", expanded=True):
            st.json(inspection.matched_fields)

        if inspection.missing_preferred_fields:
            st.warning("Some preferred fields are still missing: " + ", ".join(inspection.missing_preferred_fields))
        else:
            st.success("Preferred market fields were found for the current handoff stage.")

        st.markdown("#### Normalized preview")
        st.dataframe(inspection.dataframe.head(25), width="stretch")

        st.info("Proceed to Module 4 when the market-data preview looks correct.")
    except Exception as exc:
        st.error(f"Market file could not be interpreted: {exc}")
