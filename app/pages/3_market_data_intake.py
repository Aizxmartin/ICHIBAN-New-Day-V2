import sys
from pathlib import Path

import pandas as pd
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

def load_market_dataframe(uploaded_file):
    uploaded_file.seek(0)

    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        uploaded_file.seek(0)
        raw = pd.read_excel(uploaded_file, header=None)

        header_row = None
        required_header_markers = {
            "List Price",
            "Above Grade Finished Area",
            "Street Number Numeric",
            "Street Name",
        }

        for i in range(min(30, len(raw))):
            values = {str(v).strip() for v in raw.iloc[i].tolist()}
            matches = required_header_markers.intersection(values)

            if len(matches) >= 3:
                header_row = i
                break

        if header_row is None:
            header_row = 0

        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, header=header_row)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")

    return df
               
if uploaded_file is not None:
    st.session_state["market_file"] = uploaded_file

    try:
        df = load_market_dataframe(uploaded_file)
        inspection = inspect_market_file(df)

        st.session_state["market_inspection"] = {
            "detected_header_row": inspection.detected_header_row,
            "header_score": inspection.header_score,
            "matched_fields": inspection.matched_fields,
            "missing_preferred_fields": inspection.missing_preferred_fields,
            "rows_loaded": int(len(inspection.dataframe)),
            "normalized_columns": list(inspection.dataframe.columns),
        }

        st.session_state["market_data_normalized"] = inspection.dataframe

        st.success("Market file loaded and normalized.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Rows loaded", int(len(inspection.dataframe)))
        c2.metric("Detected header row", inspection.detected_header_row)
        c3.metric("Header score", inspection.header_score)

        with st.expander("Matched MLS fields", expanded=True):
            st.json(inspection.matched_fields)

        if inspection.missing_preferred_fields:
            st.warning(
                "Some preferred fields are still missing: "
                + ", ".join(inspection.missing_preferred_fields)
            )
        else:
            st.success("Preferred market fields were found for the current handoff stage.")

        st.markdown("#### Normalized preview")
        preview_df = inspection.dataframe.head(25).copy()
        for col in preview_df.columns:
            if preview_df[col].dtype == "object":
                preview_df[col] = preview_df[col].astype(str)
        st.dataframe(preview_df, width="stretch")

        st.info("Proceed to Module 4 when the market-data preview looks correct.")

    except Exception as exc:
        st.error(f"Market file could not be interpreted: {exc}")