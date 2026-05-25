from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.subject_acquisition import load_verified_subject
from core.market_conditions import load_verified_1004mc


st.set_page_config(
    page_title="ICHIBAN - Valuation Run",
    page_icon="🏁",
    layout="wide",
)

st.title("Module 4 — Valuation Run")
st.subheader("Run valuation using the locked subject, valuation comps, and optional competition/momentum file")


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

REPORT_TYPE_OPTIONS = [
    "Seller Report Package — Full Default",
    "Seller Report Package — Summary",
    "Internal Review Package",
    "Valuation JSON Only",
]

DEFAULT_REPORT_TYPE = "Seller Report Package — Full Default"

REPORT_LANGUAGE_RULE = (
    "The value range is based on closed comparable evidence. The market momentum section reviews a broader "
    "competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction."
)

MARKET_WORKFLOW_RULE = {
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


# ---------------------------------------------------------------------
# Report package setting — intentionally outside any manual-entry section
# ---------------------------------------------------------------------

stored_report_type = st.session_state.get("report_type_selection", DEFAULT_REPORT_TYPE)
if stored_report_type not in REPORT_TYPE_OPTIONS:
    stored_report_type = DEFAULT_REPORT_TYPE

report_type = st.selectbox(
    "Report Type",
    REPORT_TYPE_OPTIONS,
    index=REPORT_TYPE_OPTIONS.index(stored_report_type),
    key="report_type_selection",
    help="Default is the full seller-facing report package. This is separate from manual 1004MC entry.",
)

st.caption(
    "Default report type is Seller Report Package — Full Default. The valuation comp file supports value; "
    "the 1004MC / Competition Market File supports momentum and market-pattern commentary."
)

st.session_state["market_workflow_rule"] = st.session_state.get("market_workflow_rule") or MARKET_WORKFLOW_RULE
st.session_state["report_language_rule"] = st.session_state.get("report_language_rule") or REPORT_LANGUAGE_RULE


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """
    Convert objects into JSON-safe structures.
    Handles pandas DataFrames, Paths, and other non-serializable values.
    """

    if value is None:
        return None

    if hasattr(value, "to_dict") and hasattr(value, "columns"):
        # pandas DataFrame
        try:
            return value.to_dict(orient="records")
        except Exception:
            return str(value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _save_json(path: str | Path, data: Dict[str, Any]) -> Path:
    save_path = Path(path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(data), f, indent=2)

    return save_path


def _load_subject_profile() -> Tuple[Dict[str, Any], bool, str]:
    """
    Load subject from session first, then from data/verified_subject.json.
    """

    session_subject = st.session_state.get("subject_profile") or {}
    saved_subject = load_verified_subject() or {}

    subject = session_subject or saved_subject or {}

    if saved_subject and not session_subject:
        st.session_state["subject_profile"] = saved_subject
        subject = saved_subject

    subject_ready = bool(
        subject.get("subject_verified")
        or subject.get("subject_profile_ready")
        or st.session_state.get("subject_ready")
    )

    if subject_ready:
        st.session_state["subject_ready"] = True

    source = "session_state"
    if saved_subject and subject == saved_subject:
        source = "data/verified_subject.json"

    return subject, subject_ready, source


def _load_valuation_comp_data() -> Tuple[Any, bool, str]:
    """
    Load the focused valuation comp file.

    During the transition from one generic market file to two file roles, the
    legacy market_data_normalized key is still accepted as a fallback.
    """

    valuation_df = st.session_state.get("valuation_comp_data_normalized")
    if valuation_df is not None:
        return valuation_df, True, "session_state.valuation_comp_data_normalized"

    legacy_market_df = st.session_state.get("market_data_normalized")
    if legacy_market_df is not None:
        return legacy_market_df, True, "session_state.market_data_normalized legacy fallback"

    return None, False, "not_found"


def _load_competition_market_data() -> Tuple[Any, bool, str]:
    """
    Load the broader 1004MC / competition market file.

    This file is optional. It should not replace the valuation comp file.
    """

    competition_df = st.session_state.get("competition_market_data_normalized")
    if competition_df is not None:
        return competition_df, True, "session_state.competition_market_data_normalized"

    market_pattern_df = st.session_state.get("market_pattern_data_normalized")
    if market_pattern_df is not None:
        return market_pattern_df, True, "session_state.market_pattern_data_normalized"

    return None, False, "not_found"


def _load_1004mc_summary() -> Tuple[Dict[str, Any], bool, str]:
    """
    Load 1004MC from session first, then from data/verified_1004mc.json.
    """

    session_1004mc = (
        st.session_state.get("one_hundred_four_mc_summary")
        or st.session_state.get("market_conditions_1004mc")
        or {}
    )

    saved_1004mc = load_verified_1004mc() or {}

    summary = session_1004mc or saved_1004mc or {}

    if saved_1004mc and not session_1004mc:
        st.session_state["one_hundred_four_mc_summary"] = saved_1004mc
        st.session_state["market_conditions_1004mc"] = saved_1004mc
        summary = saved_1004mc

    supplied = bool(
        summary.get("market_conditions_verified")
        or summary.get("is_supplied")
        or summary.get("recommended_route") == "parsed_1004mc_coordinate_table"
        or summary.get("current_3_sales") is not None
        or summary.get("annual_market_change_percent") is not None
        or summary.get("monthly_market_change_percent") is not None
    )

    source = "session_state"
    if saved_1004mc and summary == saved_1004mc:
        source = "data/verified_1004mc.json"

    return summary, supplied, source


def _row_count(dataframe: Any) -> int:
    if dataframe is None:
        return 0

    try:
        return int(len(dataframe))
    except Exception:
        return 0


def _try_run_valuation_engine(
    subject_profile: Dict[str, Any],
    valuation_comp_data: Any,
    one_hundred_four_mc_summary: Dict[str, Any],
    competition_market_data: Any = None,
    selected_report_type: str = DEFAULT_REPORT_TYPE,
) -> Dict[str, Any]:
    """
    Try to call the existing valuation engine without assuming the exact function name.

    This lets Module 4 work while the valuation engine is still evolving.
    If no engine function is found, this returns a structured fallback package
    so the inputs can still be inspected.
    """

    candidates = [
        ("core.valuation_engine", "run_valuation_engine"),
        ("core.valuation_engine", "run_valuation"),
        ("core.valuation_engine", "run_base_valuation"),
        ("core.valuation_run", "run_valuation_engine"),
        ("core.valuation_run", "run_valuation"),
        ("core.engine.valuation_engine", "run_valuation_engine"),
        ("core.engine.valuation_engine", "run_valuation"),
    ]

    last_errors = []

    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(module_name)
            func = getattr(module, function_name, None)

            if func is None:
                continue

            try:
                signature = inspect.signature(func)
                params = signature.parameters

                kwargs = {}

                if "subject_profile" in params:
                    kwargs["subject_profile"] = subject_profile
                if "subject" in params:
                    kwargs["subject"] = subject_profile

                if "market_data" in params:
                    kwargs["market_data"] = valuation_comp_data
                if "market_df" in params:
                    kwargs["market_df"] = valuation_comp_data
                if "market_data_normalized" in params:
                    kwargs["market_data_normalized"] = valuation_comp_data
                if "valuation_comp_data" in params:
                    kwargs["valuation_comp_data"] = valuation_comp_data
                if "valuation_comp_df" in params:
                    kwargs["valuation_comp_df"] = valuation_comp_data

                if "competition_market_data" in params:
                    kwargs["competition_market_data"] = competition_market_data
                if "competition_market_df" in params:
                    kwargs["competition_market_df"] = competition_market_data
                if "market_pattern_data" in params:
                    kwargs["market_pattern_data"] = competition_market_data
                if "momentum_market_data" in params:
                    kwargs["momentum_market_data"] = competition_market_data

                if "one_hundred_four_mc_summary" in params:
                    kwargs["one_hundred_four_mc_summary"] = one_hundred_four_mc_summary
                if "market_conditions" in params:
                    kwargs["market_conditions"] = one_hundred_four_mc_summary
                if "mc_1004" in params:
                    kwargs["mc_1004"] = one_hundred_four_mc_summary

                if "report_type" in params:
                    kwargs["report_type"] = selected_report_type
                if "selected_report_type" in params:
                    kwargs["selected_report_type"] = selected_report_type
                if "market_workflow_rule" in params:
                    kwargs["market_workflow_rule"] = MARKET_WORKFLOW_RULE

                if kwargs:
                    output = func(**kwargs)
                else:
                    output = func(subject_profile, valuation_comp_data, one_hundred_four_mc_summary)

                return {
                    "engine_status": "success",
                    "engine_module": module_name,
                    "engine_function": function_name,
                    "report_type": selected_report_type,
                    "engine_output": _json_safe(output),
                }

            except TypeError:
                # Try common positional signature for older engine versions.
                try:
                    output = func(subject_profile, valuation_comp_data, one_hundred_four_mc_summary)
                    return {
                        "engine_status": "success",
                        "engine_module": module_name,
                        "engine_function": function_name,
                        "report_type": selected_report_type,
                        "engine_output": _json_safe(output),
                    }
                except Exception as exc:
                    last_errors.append(f"{module_name}.{function_name}: {exc}")

            except Exception as exc:
                last_errors.append(f"{module_name}.{function_name}: {exc}")

        except Exception as exc:
            last_errors.append(f"{module_name}: {exc}")

    return {
        "engine_status": "no_engine_function_found",
        "message": (
            "Module 4 successfully loaded the verified subject, valuation comp data, optional 1004MC evidence, "
            "and optional competition/momentum data, but no compatible valuation engine function was found yet."
        ),
        "attempted_engine_functions": candidates,
        "errors": last_errors[-10:],
        "valuation_input_package": {
            "report_type": selected_report_type,
            "subject_profile": _json_safe(subject_profile),
            "valuation_comp_rows": _row_count(valuation_comp_data),
            "competition_market_rows": _row_count(competition_market_data),
            "one_hundred_four_mc_summary": _json_safe(one_hundred_four_mc_summary),
            "market_workflow_rule": MARKET_WORKFLOW_RULE,
        },
    }


# ---------------------------------------------------------------------
# Load handoffs
# ---------------------------------------------------------------------

subject_profile, subject_ready, subject_source = _load_subject_profile()
valuation_comp_data, valuation_comp_ready, valuation_comp_source = _load_valuation_comp_data()
competition_market_data, competition_market_ready, competition_market_source = _load_competition_market_data()
one_hundred_four_mc_summary, mc_supplied, mc_source = _load_1004mc_summary()

valuation_comp_inspection = (
    st.session_state.get("valuation_comp_inspection")
    or st.session_state.get("market_inspection")
    or {}
)
competition_market_inspection = (
    st.session_state.get("competition_market_inspection")
    or st.session_state.get("market_pattern_inspection")
    or {}
)
market_file_roles = st.session_state.get("market_file_roles") or {}


# ---------------------------------------------------------------------
# Status metrics
# ---------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)

c1.metric("Subject ready", str(subject_ready))
c2.metric("Valuation comps ready", str(valuation_comp_ready))
c3.metric("1004MC / competition file", str(competition_market_ready))
c4.metric("1004MC trend supplied", str(mc_supplied))

detail1, detail2, detail3, detail4 = st.columns(4)

detail1.caption(f"Subject source: {subject_source}")
detail2.caption(f"Valuation comps source: {valuation_comp_source}")
detail3.caption(f"Competition source: {competition_market_source}")
detail4.caption(f"1004MC source: {mc_source}")


# ---------------------------------------------------------------------
# Status warnings
# ---------------------------------------------------------------------

if not subject_ready:
    st.warning("Subject profile is not ready. Complete Module 2 first.")

if not valuation_comp_ready:
    st.warning(
        "Valuation comp data is not ready. Complete Module 3 first. "
        "If you restarted Streamlit, re-upload the Valuation Comp File in Module 3."
    )

if competition_market_ready:
    st.success(
        "1004MC / Competition Market File loaded. It can support market pattern, absorption, "
        "current competition, projected MOI range, seller caveats, and momentum discussion."
    )
else:
    st.info(
        "No broader 1004MC / Competition Market File supplied. The value range can still run from closed comps, "
        "but current competition, absorption, and momentum should be limited or caveated."
    )

if mc_supplied:
    annual = one_hundred_four_mc_summary.get("annual_market_change_percent")
    monthly = one_hundred_four_mc_summary.get("monthly_market_change_percent")
    trend = one_hundred_four_mc_summary.get("market_trend_classification", "not_supplied")

    st.success(
        f"1004MC time-trend evidence loaded. Annual trend: "
        f"{'—' if annual is None else str(annual) + '%'} | "
        f"Monthly trend: {'—' if monthly is None else str(monthly) + '%'} | "
        f"Trend class: {trend}"
    )
else:
    st.info("No verified 1004MC PDF/manual time-trend evidence supplied. This is optional.")

with st.container(border=True):
    st.markdown("### File-role rule for report logic")
    st.write(REPORT_LANGUAGE_RULE)


# ---------------------------------------------------------------------
# Expanders for verification
# ---------------------------------------------------------------------

with st.expander("Verified subject profile", expanded=False):
    if subject_profile:
        st.json(_json_safe(subject_profile))
    else:
        st.caption("No subject profile loaded.")

with st.expander("Valuation Comp File handoff", expanded=False):
    st.write(
        {
            "valuation_comp_ready": valuation_comp_ready,
            "valuation_comp_rows": _row_count(valuation_comp_data),
            "valuation_comp_inspection": _json_safe(valuation_comp_inspection),
            "used_for": MARKET_WORKFLOW_RULE["file_roles"]["valuation_comp_file"],
        }
    )

    if valuation_comp_ready:
        try:
            st.dataframe(valuation_comp_data.head(25), width="stretch")
        except Exception:
            st.write("Valuation comp data exists but could not be previewed as a dataframe.")

with st.expander("1004MC / Competition Market File handoff", expanded=False):
    st.write(
        {
            "competition_market_ready": competition_market_ready,
            "competition_market_rows": _row_count(competition_market_data),
            "competition_market_inspection": _json_safe(competition_market_inspection),
            "used_for": MARKET_WORKFLOW_RULE["file_roles"]["competition_market_file"],
            "recommended_search": MARKET_WORKFLOW_RULE["recommended_search"],
        }
    )

    if competition_market_ready:
        try:
            st.dataframe(competition_market_data.head(25), width="stretch")
        except Exception:
            st.write("Competition market data exists but could not be previewed as a dataframe.")

with st.expander("1004MC / time-trend evidence", expanded=False):
    if one_hundred_four_mc_summary:
        st.json(_json_safe(one_hundred_four_mc_summary))
    else:
        st.caption("No 1004MC PDF/manual time-trend evidence loaded.")

with st.expander("Market workflow rule", expanded=False):
    st.json(_json_safe(MARKET_WORKFLOW_RULE))


# ---------------------------------------------------------------------
# Save valuation input package
# ---------------------------------------------------------------------

valuation_input_package = {
    "report_type": report_type,
    "subject_profile": _json_safe(subject_profile),
    "valuation_comp_file": {
        "ready": valuation_comp_ready,
        "rows": _row_count(valuation_comp_data),
        "source": valuation_comp_source,
        "inspection": _json_safe(valuation_comp_inspection),
        "used_for": MARKET_WORKFLOW_RULE["file_roles"]["valuation_comp_file"],
    },
    "competition_market_file": {
        "ready": competition_market_ready,
        "rows": _row_count(competition_market_data),
        "source": competition_market_source,
        "inspection": _json_safe(competition_market_inspection),
        "used_for": MARKET_WORKFLOW_RULE["file_roles"]["competition_market_file"],
    },
    "market_file_roles": _json_safe(market_file_roles),
    "one_hundred_four_mc_summary": _json_safe(one_hundred_four_mc_summary),
    "market_workflow_rule": MARKET_WORKFLOW_RULE,
    "report_language_rule": REPORT_LANGUAGE_RULE,
}

st.session_state["valuation_input_package"] = valuation_input_package

if st.button("Save Valuation Input Package"):
    saved_path = _save_json("data/valuation_input_package.json", valuation_input_package)
    st.success(f"Valuation input package saved to {saved_path}")


# ---------------------------------------------------------------------
# Run valuation
# ---------------------------------------------------------------------

st.divider()

if subject_ready and valuation_comp_ready:
    st.success("Ready to run valuation from the Valuation Comp File.")

    if st.button("Run Valuation Engine", type="primary"):
        with st.spinner("Running valuation engine..."):
            result = _try_run_valuation_engine(
                subject_profile=subject_profile,
                valuation_comp_data=valuation_comp_data,
                one_hundred_four_mc_summary=one_hundred_four_mc_summary,
                competition_market_data=competition_market_data,
                selected_report_type=report_type,
            )

        st.session_state["valuation_engine_result"] = result

        saved_path = _save_json("data/valuation_engine_output.json", result)

        if result.get("engine_status") == "success":
            st.success(f"Valuation engine completed. Output saved to {saved_path}")
        else:
            st.warning(
                "The valuation input package loaded correctly, but no compatible valuation engine function was found yet. "
                f"Diagnostic output saved to {saved_path}"
            )

    result = st.session_state.get("valuation_engine_result")

    if result:
        st.markdown("## Engine Output")
        st.json(_json_safe(result))

        output_json = json.dumps(_json_safe(result), indent=2)

        st.download_button(
            label="Download valuation engine output JSON",
            data=output_json,
            file_name="valuation_engine_output.json",
            mime="application/json",
        )

else:
    st.info("Complete Modules 2 and 3 before running valuation.")