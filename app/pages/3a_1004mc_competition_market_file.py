from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.market_mapping import inspect_market_file


st.set_page_config(
    page_title="ICHIBAN - 1004MC Competition File",
    page_icon="📈",
    layout="wide",
)

st.title("Module 3A — 1004MC / Competition Market File")
st.subheader("Optional broader MLS market file for market pattern, absorption, and momentum")

REPORT_LANGUAGE_RULE = (
    "The value range is based on closed comparable evidence. The market momentum section reviews a broader "
    "competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction."
)

MARKET_WORKFLOW_RULE: Dict[str, Any] = {
    "workflow_name": "1004MC / Competition Market File Rule",
    "recommended_search": {
        "lookback": "12-month lookback",
        "property_type": "Single Family Residence when subject is Single Family",
        "radius": "Approximately 3-mile radius, expandable to 3–5 miles if needed",
        "price_band": "Approximately $100K below to $100K above projected range",
        "square_footage": "Use established above-grade / main-upper-level SF range parameters",
        "statuses": "Include Active, Pending, Closed, and optionally Expired/Withdrawn",
        "levels": "Levels may include all levels for competition/momentum, but level differences must be tagged",
    },
    "file_roles": {
        "valuation_comp_file": "Adjusted comps, Ruler Range, and recommended value range",
        "competition_market_file": "Market pattern, absorption, current competition, projected MOI range, seller caveats, and momentum discussion",
    },
    "report_language_rule": REPORT_LANGUAGE_RULE,
}

st.session_state["market_workflow_rule"] = MARKET_WORKFLOW_RULE
st.session_state["report_language_rule"] = REPORT_LANGUAGE_RULE

st.markdown(
    """
### Purpose

This optional file is separate from the **Valuation Comp File** uploaded in Module 3.

- **Valuation Comp File:** adjusted closed comps, Ruler Range, and recommended value range.
- **1004MC / Competition Market File:** market pattern, absorption, current competition, projected MOI range, seller caveats, and momentum discussion.

This broader file can support both the 1004MC-style market-pattern overlay and the current competition / momentum section.
"""
)

with st.expander("Recommended broader MLS search rule", expanded=True):
    st.json(MARKET_WORKFLOW_RULE["recommended_search"])

st.info(REPORT_LANGUAGE_RULE)


def _inspection_to_dict(inspection: Any) -> Dict[str, Any]:
    return {
        "detected_header_row": inspection.detected_header_row,
        "header_score": inspection.header_score,
        "matched_fields": inspection.matched_fields,
        "missing_preferred_fields": inspection.missing_preferred_fields,
        "rows_loaded": int(len(inspection.dataframe)),
        "normalized_columns": list(inspection.dataframe.columns),
    }


def _preview_dataframe(dataframe: Any) -> None:
    preview_df = dataframe.head(25).copy()

    for col in preview_df.columns:
        if preview_df[col].dtype == "object":
            preview_df[col] = preview_df[col].astype(str)

    st.dataframe(preview_df, width="stretch")


competition_market_file = st.file_uploader(
    "Upload 1004MC / Competition Market File (.xlsx or .csv)",
    type=["xlsx", "xls", "csv"],
    help=(
        "Optional broader MLS export: 12-month lookback, Active/Pending/Closed, optionally Expired/Withdrawn, "
        "about 3 miles expandable to 3–5 miles, and about $100K below/above projected range."
    ),
    key="competition_market_file_uploader",
)

if competition_market_file is not None:
    try:
        inspection = inspect_market_file(competition_market_file)
        inspection_dict = _inspection_to_dict(inspection)

        st.session_state["competition_market_data_normalized"] = inspection.dataframe
        st.session_state["competition_market_inspection"] = inspection_dict
        st.session_state["competition_market_file_name"] = competition_market_file.name

        # Future aliases for market-pattern/momentum code.
        st.session_state["market_pattern_data_normalized"] = inspection.dataframe
        st.session_state["market_pattern_inspection"] = inspection_dict

        roles = st.session_state.get("market_file_roles") or {}
        roles["competition_market_file"] = {
            "file_name": competition_market_file.name,
            "rows_loaded": inspection_dict.get("rows_loaded"),
            "used_for": MARKET_WORKFLOW_RULE["file_roles"]["competition_market_file"],
            "supports": [
                "1004MC / Market Pattern Overlay",
                "Competition / Momentum Review",
                "Projected MOI range",
                "Seller caveats",
            ],
        }
        st.session_state["market_file_roles"] = roles
        st.session_state.pop("valuation_engine_result", None)

        st.success("1004MC / Competition Market File loaded and normalized.")

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
        _preview_dataframe(inspection.dataframe)

    except Exception as exc:
        st.error(f"1004MC / Competition Market File could not be interpreted: {exc}")

else:
    existing_df = st.session_state.get("competition_market_data_normalized")
    existing_info = st.session_state.get("competition_market_inspection") or {}

    if existing_df is not None:
        st.success("1004MC / Competition Market File is already loaded in session.")
        c1, c2 = st.columns(2)
        c1.metric("Rows loaded", existing_info.get("rows_loaded", len(existing_df)))
        c2.metric("File role", "Competition / Momentum")

        with st.expander("Current competition-market handoff", expanded=False):
            st.json(
                {
                    "competition_market_file_name": st.session_state.get("competition_market_file_name"),
                    "competition_market_inspection": existing_info,
                    "market_file_roles": st.session_state.get("market_file_roles") or {},
                }
            )

        st.markdown("#### Current normalized preview")
        _preview_dataframe(existing_df)
    else:
        st.info(
            "This file is optional, but without it ICHIBAN should not overstate current competition, absorption, "
            "or momentum conclusions."
        )

st.divider()

if st.button("Continue to Module 4 — Valuation Run", type="primary"):
    st.switch_page("pages/4_valuation_run.py")
