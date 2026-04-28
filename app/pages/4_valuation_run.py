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
st.subheader("Run the valuation engine using the locked subject profile and normalized MLS data")


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


def _load_market_data() -> Tuple[Any, bool, str]:
    """
    Market data is currently still session-based because the normalized DataFrame
    is created in Module 3 from the MLS upload.

    If this shows not ready, go back to Module 3 and upload the MLS file again.
    """

    market_df = st.session_state.get("market_data_normalized")
    market_ready = market_df is not None

    if market_ready:
        return market_df, True, "session_state.market_data_normalized"

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


def _market_row_count(market_df: Any) -> int:
    if market_df is None:
        return 0

    try:
        return int(len(market_df))
    except Exception:
        return 0


def _try_run_valuation_engine(
    subject_profile: Dict[str, Any],
    market_data: Any,
    one_hundred_four_mc_summary: Dict[str, Any],
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
                    kwargs["market_data"] = market_data
                if "market_df" in params:
                    kwargs["market_df"] = market_data
                if "market_data_normalized" in params:
                    kwargs["market_data_normalized"] = market_data

                if "one_hundred_four_mc_summary" in params:
                    kwargs["one_hundred_four_mc_summary"] = one_hundred_four_mc_summary
                if "market_conditions" in params:
                    kwargs["market_conditions"] = one_hundred_four_mc_summary
                if "mc_1004" in params:
                    kwargs["mc_1004"] = one_hundred_four_mc_summary

                if kwargs:
                    output = func(**kwargs)
                else:
                    output = func(subject_profile, market_data, one_hundred_four_mc_summary)

                return {
                    "engine_status": "success",
                    "engine_module": module_name,
                    "engine_function": function_name,
                    "engine_output": _json_safe(output),
                }

            except TypeError:
                # Try common positional signature.
                try:
                    output = func(subject_profile, market_data, one_hundred_four_mc_summary)
                    return {
                        "engine_status": "success",
                        "engine_module": module_name,
                        "engine_function": function_name,
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
            "Module 4 successfully loaded the verified subject, market data, and 1004MC evidence, "
            "but no compatible valuation engine function was found yet."
        ),
        "attempted_engine_functions": candidates,
        "errors": last_errors[-10:],
        "valuation_input_package": {
            "subject_profile": _json_safe(subject_profile),
            "market_rows": _market_row_count(market_data),
            "one_hundred_four_mc_summary": _json_safe(one_hundred_four_mc_summary),
        },
    }


# ---------------------------------------------------------------------
# Load handoffs
# ---------------------------------------------------------------------

subject_profile, subject_ready, subject_source = _load_subject_profile()
market_data, market_ready, market_source = _load_market_data()
one_hundred_four_mc_summary, mc_supplied, mc_source = _load_1004mc_summary()

market_inspection = st.session_state.get("market_inspection") or {}


# ---------------------------------------------------------------------
# Status metrics
# ---------------------------------------------------------------------

c1, c2, c3 = st.columns(3)

c1.metric("Subject ready", str(subject_ready))
c2.metric("Market data ready", str(market_ready))
c3.metric("1004MC supplied", str(mc_supplied))

detail1, detail2, detail3 = st.columns(3)

detail1.caption(f"Subject source: {subject_source}")
detail2.caption(f"Market source: {market_source}")
detail3.caption(f"1004MC source: {mc_source}")


# ---------------------------------------------------------------------
# Status warnings
# ---------------------------------------------------------------------

if not subject_ready:
    st.warning("Subject profile is not ready. Complete Module 2 first.")

if not market_ready:
    st.warning(
        "Market data is not ready. Complete Module 3 first. "
        "If you restarted Streamlit, re-upload the MLS market file in Module 3."
    )

if mc_supplied:
    annual = one_hundred_four_mc_summary.get("annual_market_change_percent")
    monthly = one_hundred_four_mc_summary.get("monthly_market_change_percent")
    trend = one_hundred_four_mc_summary.get("market_trend_classification", "not_supplied")

    st.success(
        f"1004MC evidence loaded. Annual trend: "
        f"{'—' if annual is None else str(annual) + '%'} | "
        f"Monthly trend: {'—' if monthly is None else str(monthly) + '%'} | "
        f"Trend class: {trend}"
    )
else:
    st.info("No verified 1004MC evidence supplied. This is optional.")


# ---------------------------------------------------------------------
# Expanders for verification
# ---------------------------------------------------------------------

with st.expander("Verified subject profile", expanded=False):
    if subject_profile:
        st.json(_json_safe(subject_profile))
    else:
        st.caption("No subject profile loaded.")

with st.expander("Market data handoff", expanded=False):
    st.write(
        {
            "market_ready": market_ready,
            "market_rows": _market_row_count(market_data),
            "market_inspection": _json_safe(market_inspection),
        }
    )

    if market_ready:
        try:
            st.dataframe(market_data.head(25), width="stretch")
        except Exception:
            st.write("Market data exists but could not be previewed as a dataframe.")

with st.expander("1004MC / time-trend evidence", expanded=False):
    if one_hundred_four_mc_summary:
        st.json(_json_safe(one_hundred_four_mc_summary))
    else:
        st.caption("No 1004MC evidence loaded.")


# ---------------------------------------------------------------------
# Save valuation input package
# ---------------------------------------------------------------------

valuation_input_package = {
    "subject_profile": _json_safe(subject_profile),
    "market_rows": _market_row_count(market_data),
    "market_inspection": _json_safe(market_inspection),
    "one_hundred_four_mc_summary": _json_safe(one_hundred_four_mc_summary),
}

if st.button("Save Valuation Input Package"):
    saved_path = _save_json("data/valuation_input_package.json", valuation_input_package)
    st.success(f"Valuation input package saved to {saved_path}")


# ---------------------------------------------------------------------
# Run valuation
# ---------------------------------------------------------------------

st.divider()

if subject_ready and market_ready:
    st.success("Ready to run valuation.")

    if st.button("Run Valuation Engine", type="primary"):
        with st.spinner("Running valuation engine..."):
            result = _try_run_valuation_engine(
                subject_profile=subject_profile,
                market_data=market_data,
                one_hundred_four_mc_summary=one_hundred_four_mc_summary,
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