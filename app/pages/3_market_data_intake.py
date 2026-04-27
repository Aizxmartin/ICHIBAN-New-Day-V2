import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.market_mapping import inspect_market_file
from core.one_hundred_four_mc import build_1004mc_summary

st.set_page_config(page_title="ICHIBAN - Market Data Intake", page_icon="📊", layout="wide")

st.title("Module 3 — Market Data Intake")
st.subheader("Upload MLS market data, then optionally add 1004MC market-trend evidence")

st.markdown(
    """
### Intake order for Module 3
1. Upload the MLS market/comparable data file.
2. Confirm the normalized preview looks correct.
3. Optionally upload or manually enter 1004MC / market-trend evidence.

1004MC data is helpful for time-adjustment analysis, but it is **not required**. If it is not supplied,
ICHIBAN continues with comp-based evidence and notes that formal time-adjustment evidence was not supplied.
"""
)

uploaded_file = st.file_uploader(
    "1. Upload MLS export (.xlsx or .csv)",
    type=["xlsx", "xls", "csv"],
    help="Upload the MLS export that will feed comps, status review, and market interpretation.",
    key="market_file_uploader",
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
        st.session_state["market_data_normalized"] = inspection.dataframe

        st.success("Market file loaded and normalized.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Rows loaded", int(len(inspection.dataframe)))
        c2.metric("Detected header row", inspection.detected_header_row)
        c3.metric("Header score", inspection.header_score)

        with st.expander("Matched MLS fields", expanded=False):
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

    except Exception as exc:
        st.error(f"Market file could not be interpreted: {exc}")
elif st.session_state.get("market_data_normalized") is None:
    st.info("Upload the MLS market-data file to continue.")

market_ready = st.session_state.get("market_data_normalized") is not None

if market_ready:
    st.divider()
    st.markdown("## 2. Optional 1004MC / Time-Trend Evidence")
    st.caption(
        "This step happens before valuation so any annual/monthly market trend can be stored before comp time adjustments are considered. "
        "The raw 1004MC file is not retained in session state; only structured summary values are stored."
    )

    existing_1004mc = st.session_state.get("one_hundred_four_mc_summary", {}) or {}

    with st.container(border=True):
        mc_file = st.file_uploader(
            "Upload 1004MC report or market-trend support file (optional)",
            type=["pdf", "xlsx", "xls", "csv", "txt"],
            help="Optional. Upload if available. If parsing misses the rate, enter annual/monthly values manually below.",
            key="one_hundred_four_mc_file_uploader",
        )

        c1, c2, c3 = st.columns(3)
        manual_annual = c1.number_input(
            "Annual market change % (optional)",
            value=float(existing_1004mc.get("annual_market_change_percent") or 0.0),
            step=0.1,
            format="%.2f",
            help="Use positive for increasing market and negative for declining market. Leave 0 if not supplied.",
        )
        manual_monthly = c2.number_input(
            "Monthly market change % (optional)",
            value=float(existing_1004mc.get("monthly_market_change_percent") or 0.0),
            step=0.1,
            format="%.2f",
            help="If annual is supplied and monthly is left at 0, ICHIBAN can derive annual ÷ 12.",
        )
        trend_options = ["not_supplied", "increasing", "stable", "declining", "insufficient"]
        existing_trend = existing_1004mc.get("market_trend_classification") or "not_supplied"
        trend_index = trend_options.index(existing_trend) if existing_trend in trend_options else 0
        manual_trend = c3.selectbox(
            "Market trend classification",
            trend_options,
            index=trend_index,
            help="Optional. Choose not_supplied if the 1004MC data is not available.",
        )

        manual_note = st.text_area(
            "1004MC / trend note for valuation handoff (optional)",
            value=existing_1004mc.get("manual_note", ""),
            height=80,
            placeholder="Example: 1004MC indicates stable pricing over the last 12 months; use only as secondary support.",
        )

        if st.button("Save 1004MC / Time-Trend Handoff"):
            summary = build_1004mc_summary(
                uploaded_file=mc_file,
                manual_annual_percent=None if manual_annual == 0 else manual_annual,
                manual_monthly_percent=None if manual_monthly == 0 else manual_monthly,
                manual_trend=None if manual_trend == "not_supplied" else manual_trend,
                manual_note=manual_note,
            )
            st.session_state["one_hundred_four_mc_summary"] = summary
            if summary.get("is_supplied"):
                st.success("1004MC / market-trend handoff saved for Module 4.")
            else:
                st.info("No 1004MC values supplied. Module 4 will continue without formal time-trend evidence.")

    saved_summary = st.session_state.get("one_hundred_four_mc_summary")
    if saved_summary:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("1004MC Status", saved_summary.get("source_status", "not_supplied"))
        annual = saved_summary.get("annual_market_change_percent")
        monthly = saved_summary.get("monthly_market_change_percent")
        c2.metric("Annual Trend", "—" if annual is None else f"{annual:.2f}%")
        c3.metric("Monthly Trend", "—" if monthly is None else f"{monthly:.2f}%")
        c4.metric("Trend Class", saved_summary.get("market_trend_classification", "not_supplied"))

        with st.expander("1004MC structured handoff", expanded=False):
            st.json(saved_summary)
    else:
        st.info("1004MC is optional. You may proceed to Module 4 without it.")

    st.success("Proceed to Module 4 when the MLS preview and optional 1004MC handoff look correct.")
