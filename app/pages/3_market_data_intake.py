from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.market_mapping import inspect_market_file
from core.market_conditions import (
    clear_verified_1004mc,
    load_verified_1004mc,
    parse_1004mc_pdf,
    save_verified_1004mc,
)


st.set_page_config(
    page_title="ICHIBAN - Market Data Intake",
    page_icon="📊",
    layout="wide",
)

st.title("Module 3 — Market Data Intake")
st.subheader("Upload MLS valuation evidence, market momentum evidence, and optional 1004MC support")

st.markdown(
    """
### Intake order for Module 3

1. Upload the **Comparable Sales / Valuation File**.
2. Optionally use that same file for momentum if it includes multiple statuses, or upload a separate **Market Momentum / Competition File**.
3. Optionally upload, parse, or manually enter 1004MC / market-trend evidence.

ICHIBAN keeps valuation evidence and strategy evidence separate:

- **Closed comparable sales** support the value range and Ruler Range.
- **Active, Coming Soon, Pending, Closed, Withdrawn, and Expired activity** support market momentum, competition, absorption, and launch posture.
"""
)


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

TREND_OPTIONS = ["not_supplied", "increasing", "stable", "declining", "insufficient"]

PERIODS = [
    ("prior_7_12", "Prior 7–12 Months"),
    ("prior_4_6", "Prior 4–6 Months"),
    ("current_3", "Current–3 Months"),
]

CORE_1004MC_FIELDS = [
    ("sales", "Sales", "int", 1),
    ("absorption_rate", "Absorption Rate", "float", 0.01),
    ("active_listings", "Active Listings", "int", 1),
    ("months_supply", "Months Supply", "float", 0.01),
    ("median_close_price", "Median Close Price", "int", 1000),
    ("median_sales_dim", "Median Sales DIM", "int", 1),
]

ADDITIONAL_1004MC_FIELDS = [
    ("median_list_price", "Median List Price", "int", 1000),
    ("median_listings_dim", "Median Listings DIM", "int", 1),
    ("median_sale_to_list_price_pct", "Sale/List %", "float", 0.01),
]

STATUS_GROUPS = {
    "closed": ["closed", "sold"],
    "active": ["active"],
    "coming_soon": ["coming soon", "comingsoon"],
    "pending": ["pending", "under contract", "active under contract"],
    "withdrawn_expired": ["withdrawn", "expired", "cancelled", "canceled"],
}

# These are base widget keys. The live Streamlit widget key appends a reset id.
# This solves the "Clear 1004MC did not clear fields on screen" issue.
BASE_WIDGET_TO_DATA_KEY: Dict[str, str] = {}

for period_key, _period_label in PERIODS:
    for suffix, _label, _kind, _step in CORE_1004MC_FIELDS + ADDITIONAL_1004MC_FIELDS:
        BASE_WIDGET_TO_DATA_KEY[f"{period_key}_{suffix}_input"] = f"{period_key}_{suffix}"

BASE_WIDGET_TO_DATA_KEY.update(
    {
        "annual_market_change_percent_input": "annual_market_change_percent",
        "monthly_market_change_percent_input": "monthly_market_change_percent",
    }
)

BASE_SPECIAL_1004MC_WIDGET_KEYS = [
    "market_trend_classification_input",
    "manual_1004mc_note_input",
    "auto_calc_1004mc_trend_checkbox",
]


# ---------------------------------------------------------------------
# 1004MC reset state
# ---------------------------------------------------------------------

if "1004mc_widget_reset_id" not in st.session_state:
    st.session_state["1004mc_widget_reset_id"] = 0


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(str(value).replace(",", "").replace("$", "").replace("%", "")))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").replace("$", "").replace("%", ""))
    except Exception:
        return 0.0


def _none_if_zero_int(value: int) -> Optional[int]:
    return None if value == 0 else value


def _none_if_zero_float(value: float) -> Optional[float]:
    return None if value == 0 else value


def _widget_key(base_key: str) -> str:
    """
    Return the current live Streamlit widget key.

    Changing 1004mc_widget_reset_id forces Streamlit to construct brand-new
    widgets, which reliably clears old values from the visible screen.
    """

    return f"{base_key}_{st.session_state.get('1004mc_widget_reset_id', 0)}"


def _widget_value_to_data_value(base_widget_key: str, value: Any) -> Any:
    if (
        "rate" in base_widget_key
        or "supply" in base_widget_key
        or "percent" in base_widget_key
        or "pct" in base_widget_key
    ):
        value = _safe_float(value)
        return _none_if_zero_float(value)

    value = _safe_int(value)
    return _none_if_zero_int(value)


def _render_metric_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


# ---------------------------------------------------------------------
# Market file helpers
# ---------------------------------------------------------------------

def _summarize_statuses(df: Any) -> Dict[str, Any]:
    if df is None:
        return {
            "rows": 0,
            "has_status_column": False,
            "counts": {},
            "group_counts": {},
            "distinct_statuses": 0,
        }

    rows = int(len(df))

    if "mls_status" not in df.columns:
        return {
            "rows": rows,
            "has_status_column": False,
            "counts": {},
            "group_counts": {},
            "distinct_statuses": 0,
        }

    status_series = df["mls_status"].fillna("Unknown").astype(str).str.strip()
    counts = status_series.value_counts(dropna=False).to_dict()
    group_counts = {group: 0 for group in STATUS_GROUPS}

    for raw_status, count in counts.items():
        status_norm = str(raw_status).strip().lower()
        for group, terms in STATUS_GROUPS.items():
            if any(term in status_norm for term in terms):
                group_counts[group] += int(count)

    return {
        "rows": rows,
        "has_status_column": True,
        "counts": {str(k): int(v) for k, v in counts.items()},
        "group_counts": group_counts,
        "distinct_statuses": int(len(counts)),
    }


def _has_column(df: Any, column_name: str) -> bool:
    return df is not None and column_name in df.columns


def _supports_valuation(df: Any, status_summary: Dict[str, Any]) -> bool:
    if df is None:
        return False

    group_counts = status_summary.get("group_counts", {})
    closed_count = int(group_counts.get("closed", 0))

    has_price_evidence = _has_column(df, "close_price") or _has_column(df, "net_close_price")
    return closed_count > 0 or has_price_evidence


def _supports_momentum(status_summary: Dict[str, Any]) -> bool:
    if not status_summary.get("has_status_column"):
        return False

    group_counts = status_summary.get("group_counts", {})

    active_like = int(group_counts.get("active", 0)) + int(group_counts.get("coming_soon", 0))
    pending_count = int(group_counts.get("pending", 0))
    closed_count = int(group_counts.get("closed", 0))
    distinct_statuses = int(status_summary.get("distinct_statuses", 0))

    return distinct_statuses >= 2 and (active_like > 0 or pending_count > 0) and closed_count > 0


def _inspection_to_dict(inspection: Any) -> Dict[str, Any]:
    return {
        "detected_header_row": inspection.detected_header_row,
        "header_score": inspection.header_score,
        "matched_fields": inspection.matched_fields,
        "missing_preferred_fields": inspection.missing_preferred_fields,
        "rows_loaded": int(len(inspection.dataframe)),
        "normalized_columns": list(inspection.dataframe.columns),
    }


def _render_status_summary(label: str, status_summary: Dict[str, Any]) -> None:
    st.markdown(f"#### {label} Status Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", status_summary.get("rows", 0))
    c2.metric("Status Column", "Yes" if status_summary.get("has_status_column") else "No")
    c3.metric("Distinct Statuses", status_summary.get("distinct_statuses", 0))
    c4.metric("Closed / Sold", status_summary.get("group_counts", {}).get("closed", 0))

    group_counts = status_summary.get("group_counts", {}) or {}
    if group_counts:
        st.caption(
            " | ".join(
                [
                    f"Active: {group_counts.get('active', 0)}",
                    f"Coming Soon: {group_counts.get('coming_soon', 0)}",
                    f"Pending: {group_counts.get('pending', 0)}",
                    f"Withdrawn/Expired: {group_counts.get('withdrawn_expired', 0)}",
                ]
            )
        )

    if status_summary.get("counts"):
        status_rows = [
            {"Mls Status": status, "Count": count}
            for status, count in status_summary.get("counts", {}).items()
        ]
        st.dataframe(status_rows, width="stretch", hide_index=True)
    else:
        st.caption("No Mls Status values were detected.")


def _render_normalized_preview(label: str, df: Any) -> None:
    st.markdown(f"#### {label} normalized preview")
    preview_df = df.head(25).copy()

    for col in preview_df.columns:
        if preview_df[col].dtype == "object":
            preview_df[col] = preview_df[col].astype(str)

    st.dataframe(preview_df, width="stretch")


def _inspect_and_store_market_file(uploaded_file: Any, role: str) -> Optional[Any]:
    try:
        inspection = inspect_market_file(uploaded_file)
        df = inspection.dataframe
        status_summary = _summarize_statuses(df)
        inspection_dict = _inspection_to_dict(inspection)

        if role == "valuation":
            st.session_state["valuation_file"] = uploaded_file
            st.session_state["valuation_file_df"] = df
            st.session_state["valuation_market_inspection"] = inspection_dict
            st.session_state["valuation_status_summary"] = status_summary

            # Backward compatibility for Module 4 and older code.
            st.session_state["market_file"] = uploaded_file
            st.session_state["market_data_normalized"] = df
            st.session_state["market_inspection"] = inspection_dict

        elif role == "momentum":
            st.session_state["momentum_file"] = uploaded_file
            st.session_state["momentum_file_df"] = df
            st.session_state["momentum_market_inspection"] = inspection_dict
            st.session_state["momentum_status_summary"] = status_summary

        # New market data invalidates prior valuation output.
        st.session_state.pop("valuation_engine_result", None)
        st.session_state.pop("valuation_input_package", None)

        return inspection

    except Exception as exc:
        st.error(f"{role.title()} file could not be interpreted: {exc}")
        return None


# ---------------------------------------------------------------------
# 1004MC helpers
# ---------------------------------------------------------------------

def _clear_1004mc_widget_state() -> None:
    """
    Clear 1004MC widgets, parsed values, saved handoff values, and stale valuation output.

    Important:
    Streamlit file uploaders and number inputs can keep visible values even after
    st.session_state.pop() if the same widget key is reused. The reliable reset is
    to remove known state AND increment 1004mc_widget_reset_id before rerun.
    """

    exact_keys_to_clear = {
        "market_conditions_1004mc",
        "one_hundred_four_mc_summary",
        "1004mc_pending_widget_load",
        "valuation_engine_result",
        "valuation_input_package",
    }

    base_prefixes_to_clear = set(BASE_WIDGET_TO_DATA_KEY.keys())
    base_prefixes_to_clear.update(BASE_SPECIAL_1004MC_WIDGET_KEYS)
    base_prefixes_to_clear.add("one_hundred_four_mc_file_uploader")

    for key in list(st.session_state.keys()):
        if key in exact_keys_to_clear:
            st.session_state.pop(key, None)
            continue

        if any(key == prefix or key.startswith(f"{prefix}_") for prefix in base_prefixes_to_clear):
            st.session_state.pop(key, None)


def _load_1004mc_values_into_widget_state(data: Dict[str, Any], overwrite: bool = True) -> None:
    """
    Push parsed/saved 1004MC values into the current dynamic widget keys.

    This must be called BEFORE the widgets with these keys are instantiated.
    """

    for base_widget_key, data_key in BASE_WIDGET_TO_DATA_KEY.items():
        live_widget_key = _widget_key(base_widget_key)

        if overwrite or live_widget_key not in st.session_state:
            value = data.get(data_key)

            if (
                "rate" in base_widget_key
                or "supply" in base_widget_key
                or "percent" in base_widget_key
                or "pct" in base_widget_key
            ):
                st.session_state[live_widget_key] = _safe_float(value)
            else:
                st.session_state[live_widget_key] = _safe_int(value)

    trend = data.get("market_trend_classification") or "not_supplied"
    if trend not in TREND_OPTIONS:
        trend = "not_supplied"

    trend_key = _widget_key("market_trend_classification_input")
    if overwrite or trend_key not in st.session_state:
        st.session_state[trend_key] = trend

    note_key = _widget_key("manual_1004mc_note_input")
    if overwrite or note_key not in st.session_state:
        st.session_state[note_key] = data.get("manual_note") or data.get("trend_note") or ""

    auto_calc_key = _widget_key("auto_calc_1004mc_trend_checkbox")
    if overwrite or auto_calc_key not in st.session_state:
        st.session_state[auto_calc_key] = True


def _calc_market_change_from_1004mc(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive a simple market trend from median close prices.

    Conservative default:
    Compare Prior 7-12 Months median close price to Current-3 Months median close price.
    The midpoint distance is approximately 7.5 months.

    This creates a trend support indicator. It should not automatically force
    time adjustments without later valuation-engine logic and agent review.
    """

    prior = data.get("prior_7_12_median_close_price")
    current = data.get("current_3_median_close_price")

    if not prior or not current or prior <= 0:
        data["annual_market_change_percent"] = data.get("annual_market_change_percent")
        data["monthly_market_change_percent"] = data.get("monthly_market_change_percent")
        data["market_trend_classification"] = data.get("market_trend_classification") or "not_supplied"
        return data

    change_pct = ((current - prior) / prior) * 100.0
    monthly_pct = change_pct / 7.5
    annual_pct = monthly_pct * 12.0

    data["annual_market_change_percent"] = round(annual_pct, 2)
    data["monthly_market_change_percent"] = round(monthly_pct, 2)

    if monthly_pct >= 0.5:
        data["market_trend_classification"] = "increasing"
    elif monthly_pct <= -0.5:
        data["market_trend_classification"] = "declining"
    else:
        data["market_trend_classification"] = "stable"

    return data


def _build_module4_compatible_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Module 4 expects one_hundred_four_mc_summary-style keys.
    This function keeps backward compatibility while preserving the richer parser fields.
    """

    annual = data.get("annual_market_change_percent")
    monthly = data.get("monthly_market_change_percent")
    trend = data.get("market_trend_classification") or "not_supplied"

    has_structured_values = any(
        data.get(key) is not None
        for key in [
            "prior_7_12_sales",
            "prior_4_6_sales",
            "current_3_sales",
            "prior_7_12_median_close_price",
            "prior_4_6_median_close_price",
            "current_3_median_close_price",
        ]
    )

    is_supplied = bool(
        has_structured_values
        or annual is not None
        or monthly is not None
        or trend != "not_supplied"
        or data.get("manual_note")
        or data.get("trend_note")
    )

    source_status = data.get("recommended_route") or data.get("source_status") or "not_supplied"

    if is_supplied and source_status == "not_supplied":
        source_status = "verified"

    summary = dict(data)
    summary.update(
        {
            "is_supplied": is_supplied,
            "source_status": source_status,
            "annual_market_change_percent": annual,
            "monthly_market_change_percent": monthly,
            "market_trend_classification": trend,
            "manual_note": data.get("manual_note") or data.get("trend_note") or "",
        }
    )

    return summary


def _save_1004mc_to_session_and_disk(data: Dict[str, Any]) -> Path:
    """
    Save verified 1004MC data to disk and session state.
    """

    summary = _build_module4_compatible_summary(data)
    save_path = save_verified_1004mc(summary)

    st.session_state["market_conditions_1004mc"] = summary
    st.session_state["one_hundred_four_mc_summary"] = summary

    # A new 1004MC handoff invalidates any prior valuation output.
    st.session_state.pop("valuation_engine_result", None)

    return save_path


def _collect_1004mc_from_widgets(parsed_or_existing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect current dynamic 1004MC widget values into structured data.
    """

    data = dict(parsed_or_existing)
    data["source"] = "1004mc"

    for base_widget_key, data_key in BASE_WIDGET_TO_DATA_KEY.items():
        live_widget_key = _widget_key(base_widget_key)
        data[data_key] = _widget_value_to_data_value(
            base_widget_key,
            st.session_state.get(live_widget_key),
        )

    trend_key = _widget_key("market_trend_classification_input")
    market_trend = st.session_state.get(trend_key, "not_supplied")
    if market_trend not in TREND_OPTIONS:
        market_trend = "not_supplied"

    note_key = _widget_key("manual_1004mc_note_input")
    manual_note = st.session_state.get(note_key, "") or ""

    data["market_trend_classification"] = market_trend
    data["manual_note"] = manual_note.strip()
    data["trend_note"] = manual_note.strip()

    return data


# ---------------------------------------------------------------------
# 1. MLS Market Data Upload
# ---------------------------------------------------------------------

st.markdown("## 1. MLS Market Data Upload")

valuation_file = st.file_uploader(
    "1. Upload Comparable Sales / Valuation File (.xlsx or .csv)",
    type=["xlsx", "xls", "csv"],
    help="This file should contain closed comparable sales used to support the value range / Ruler Range.",
    key="valuation_file_uploader",
)

if valuation_file is not None:
    valuation_inspection = _inspect_and_store_market_file(valuation_file, "valuation")

    if valuation_inspection is not None:
        st.success("Comparable Sales / Valuation file loaded and normalized.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Rows loaded", int(len(valuation_inspection.dataframe)))
        c2.metric("Detected header row", valuation_inspection.detected_header_row)
        c3.metric("Header score", valuation_inspection.header_score)

        with st.expander("Valuation file matched MLS fields", expanded=False):
            st.json(valuation_inspection.matched_fields)

        if valuation_inspection.missing_preferred_fields:
            st.warning(
                "Some preferred valuation fields are still missing: "
                + ", ".join(valuation_inspection.missing_preferred_fields)
            )
        else:
            st.success("Preferred valuation fields were found for the current handoff stage.")

        _render_status_summary(
            "Comparable Sales / Valuation File",
            st.session_state.get("valuation_status_summary", {}),
        )
        _render_normalized_preview("Valuation file", valuation_inspection.dataframe)

elif st.session_state.get("valuation_file_df") is None:
    st.info("Upload the Comparable Sales / Valuation file to continue.")

valuation_df = st.session_state.get("valuation_file_df")
valuation_status_summary = st.session_state.get("valuation_status_summary", {})
valuation_ready = _supports_valuation(valuation_df, valuation_status_summary)

if valuation_df is not None and not valuation_ready:
    st.warning(
        "The valuation file loaded, but ICHIBAN does not yet see clear closed-price evidence. "
        "Confirm the file includes Closed/Sold rows, Close Price, or Net Close Price."
    )

st.divider()

same_file_disabled = valuation_df is None
use_same_file = st.checkbox(
    "Use the Comparable Sales file for both valuation and momentum if it contains multiple statuses",
    value=bool(st.session_state.get("use_same_file_for_momentum", False)),
    disabled=same_file_disabled,
    help=(
        "Use this only when the uploaded MLS file includes broader activity such as Active, "
        "Coming Soon, Pending, and Closed rows."
    ),
    key="use_same_file_for_momentum_checkbox",
)

st.session_state["use_same_file_for_momentum"] = bool(use_same_file)

if use_same_file and valuation_df is not None:
    st.session_state["momentum_file_df"] = valuation_df
    st.session_state["momentum_status_summary"] = valuation_status_summary
    st.session_state["momentum_market_inspection"] = st.session_state.get("valuation_market_inspection", {})
    st.info("The Comparable Sales file is currently being used for both valuation and momentum review.")

else:
    momentum_file = st.file_uploader(
        "2. Upload Market Momentum / Competition File (.xlsx or .csv) — optional",
        type=["xlsx", "xls", "csv"],
        help=(
            "This broader file should include Active, Coming Soon, Pending, Closed, and optionally "
            "Withdrawn/Expired listings for current market speed and competition review."
        ),
        key="momentum_file_uploader",
    )

    if momentum_file is not None:
        momentum_inspection = _inspect_and_store_market_file(momentum_file, "momentum")

        if momentum_inspection is not None:
            st.success("Market Momentum / Competition file loaded and normalized.")

            c1, c2, c3 = st.columns(3)
            c1.metric("Rows loaded", int(len(momentum_inspection.dataframe)))
            c2.metric("Detected header row", momentum_inspection.detected_header_row)
            c3.metric("Header score", momentum_inspection.header_score)

            with st.expander("Momentum file matched MLS fields", expanded=False):
                st.json(momentum_inspection.matched_fields)

            if momentum_inspection.missing_preferred_fields:
                st.warning(
                    "Some preferred momentum fields are still missing: "
                    + ", ".join(momentum_inspection.missing_preferred_fields)
                )
            else:
                st.success("Preferred momentum fields were found for the current handoff stage.")

            _render_status_summary(
                "Market Momentum / Competition File",
                st.session_state.get("momentum_status_summary", {}),
            )
            _render_normalized_preview("Momentum file", momentum_inspection.dataframe)

momentum_df = st.session_state.get("momentum_file_df")
momentum_status_summary = st.session_state.get("momentum_status_summary", {})
momentum_ready = _supports_momentum(momentum_status_summary)

st.divider()
st.markdown("### Market Data Readiness")

r1, r2, r3 = st.columns(3)
r1.metric("Valuation Evidence", "Ready" if valuation_ready else "Missing")
r2.metric("Momentum Evidence", "Ready" if momentum_ready else "Limited / Missing")
r3.metric("Workflow", "One File" if use_same_file else "Two File / Optional")

if valuation_ready:
    st.success("Closed comparable evidence is available for valuation support and Ruler Range development.")
else:
    st.info("Upload a Comparable Sales / Valuation file with closed sales before running the valuation engine.")

if momentum_ready:
    st.success(
        "Broader market activity is available for Momentum, competition, absorption, and launch-strategy review."
    )
else:
    st.warning(
        "Momentum is limited. This section requires broader Active, Coming Soon, Pending, and Closed market data "
        "before current competition and absorption can be evaluated with confidence."
    )

with st.expander("Market data handoff summary", expanded=False):
    st.json(
        {
            "valuation_ready": valuation_ready,
            "momentum_ready": momentum_ready,
            "use_same_file_for_momentum": bool(use_same_file),
            "valuation_status_summary": valuation_status_summary,
            "momentum_status_summary": momentum_status_summary,
            "session_state_keys": {
                "valuation_file_df": valuation_df is not None,
                "momentum_file_df": momentum_df is not None,
                "market_data_normalized_backward_compatibility": st.session_state.get("market_data_normalized") is not None,
            },
        }
    )

market_ready = valuation_ready


# ---------------------------------------------------------------------
# 2. Optional 1004MC / Time-Trend Evidence
# ---------------------------------------------------------------------

if market_ready:
    st.divider()

    st.markdown("## 2. Optional 1004MC / Time-Trend Evidence")
    st.caption(
        "This step happens before valuation so any annual/monthly market trend can be stored before comp time adjustments are considered. "
        "The raw 1004MC file is not retained in session state; only structured summary values are stored."
    )

    existing_saved_1004mc = load_verified_1004mc() or {}
    existing_session_1004mc = st.session_state.get("market_conditions_1004mc", {}) or {}
    existing_1004mc = existing_session_1004mc or existing_saved_1004mc

    # Load parsed/saved values into the widgets BEFORE the widgets are created.
    if st.session_state.get("1004mc_pending_widget_load") and existing_1004mc:
        _load_1004mc_values_into_widget_state(existing_1004mc, overwrite=True)
        st.session_state["1004mc_pending_widget_load"] = False
    elif existing_1004mc:
        _load_1004mc_values_into_widget_state(existing_1004mc, overwrite=False)

    message = st.session_state.pop("1004mc_message", None)
    if message:
        message_type = message.get("type", "info")
        message_text = message.get("text", "")

        if message_type == "success":
            st.success(message_text)
        elif message_type == "warning":
            st.warning(message_text)
        elif message_type == "error":
            st.error(message_text)
        else:
            st.info(message_text)

    with st.container(border=True):
        uploader_key = _widget_key("one_hundred_four_mc_file_uploader")

        mc_file = st.file_uploader(
            "Upload 1004MC report or market-trend support file (optional)",
            type=["pdf"],
            help=(
                "For best results, use the direct 1004MC report download/export. "
                "Avoid Microsoft Print to PDF because it may produce an image-only file."
            ),
            key=uploader_key,
        )

        col_parse, col_clear = st.columns([1, 1])

        with col_parse:
            parse_clicked = st.button("Parse 1004MC PDF", type="primary")

        with col_clear:
            clear_clicked = st.button("Clear Verified 1004MC")

        if clear_clicked:
            file_deleted = clear_verified_1004mc()
            _clear_1004mc_widget_state()
            st.session_state["1004mc_widget_reset_id"] = st.session_state.get("1004mc_widget_reset_id", 0) + 1
            st.session_state["1004mc_message"] = {
                "type": "success",
                "text": (
                    "Verified 1004MC data cleared and screen fields reset. "
                    + ("Saved JSON file was deleted." if file_deleted else "No saved JSON file was found.")
                ),
            }
            st.rerun()

        if parse_clicked:
            if mc_file is None:
                st.error("Please upload a 1004MC PDF first.")
                st.stop()

            suffix = Path(mc_file.name).suffix or ".pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(mc_file.getbuffer())
                temp_path = tmp.name

            parsed_result = parse_1004mc_pdf(temp_path).to_dict()
            parsed_result["uploaded_file_name"] = mc_file.name

            st.session_state["market_conditions_1004mc"] = parsed_result
            st.session_state["one_hundred_four_mc_summary"] = _build_module4_compatible_summary(parsed_result)
            st.session_state["1004mc_pending_widget_load"] = True
            st.session_state.pop("valuation_engine_result", None)

            route = parsed_result.get("recommended_route")
            confidence = parsed_result.get("parser_confidence")
            method = parsed_result.get("parser_method")

            if route == "parsed_1004mc_coordinate_table" and confidence == "high":
                st.session_state["1004mc_message"] = {
                    "type": "success",
                    "text": "1004MC parsed and passed validation.",
                }
            elif route == "manual_1004mc_entry_or_ocr":
                st.session_state["1004mc_message"] = {
                    "type": "warning",
                    "text": (
                        "This 1004MC appears image-only or rotated. Use direct download/export if available, "
                        "or enter values manually below."
                    ),
                }
            else:
                st.session_state["1004mc_message"] = {
                    "type": "warning",
                    "text": (
                        f"1004MC parser route: {route}. Confidence: {confidence}. Method: {method}. "
                        "Please review or correct the values below before saving."
                    ),
                }

            st.rerun()

        parsed_or_existing = st.session_state.get("market_conditions_1004mc", {}) or existing_1004mc or {}

        with st.expander("1004MC parser diagnostics", expanded=False):
            if parsed_or_existing:
                st.json(parsed_or_existing)
            else:
                st.caption("No 1004MC parser result yet.")

        st.markdown("### Verified / Manual 1004MC Values")
        st.write(
            "Review these values. If the parser did not fill them correctly, enter the values manually from the report."
        )

        columns = st.columns(3)

        for index, (period_key, period_label) in enumerate(PERIODS):
            with columns[index]:
                st.markdown(f"#### {period_label}")

                for suffix, label, kind, step in CORE_1004MC_FIELDS:
                    base_widget_key = f"{period_key}_{suffix}_input"
                    live_widget_key = _widget_key(base_widget_key)
                    full_label = f"{period_label} {label}"

                    if kind == "float":
                        st.number_input(
                            full_label,
                            min_value=0.0,
                            step=float(step),
                            format="%.2f",
                            key=live_widget_key,
                        )
                    else:
                        st.number_input(
                            full_label,
                            min_value=0,
                            step=int(step),
                            key=live_widget_key,
                        )

                with st.expander(f"{period_label} Additional Fields", expanded=False):
                    for suffix, label, kind, step in ADDITIONAL_1004MC_FIELDS:
                        base_widget_key = f"{period_key}_{suffix}_input"
                        live_widget_key = _widget_key(base_widget_key)
                        full_label = f"{period_label} {label}"

                        if kind == "float":
                            st.number_input(
                                full_label,
                                min_value=0.0,
                                step=float(step),
                                format="%.2f",
                                key=live_widget_key,
                            )
                        else:
                            st.number_input(
                                full_label,
                                min_value=0,
                                step=int(step),
                                key=live_widget_key,
                            )

        st.markdown("### Time-Trend Handoff")

        trend_col1, trend_col2, trend_col3 = st.columns(3)

        trend_col1.number_input(
            "Annual market change % (optional)",
            step=0.1,
            format="%.2f",
            help="Use positive for increasing market and negative for declining market. Leave 0 if not supplied.",
            key=_widget_key("annual_market_change_percent_input"),
        )

        trend_col2.number_input(
            "Monthly market change % (optional)",
            step=0.1,
            format="%.2f",
            help="If annual is supplied and monthly is left at 0, ICHIBAN can derive annual ÷ 12.",
            key=_widget_key("monthly_market_change_percent_input"),
        )

        trend_col3.selectbox(
            "Market trend classification",
            TREND_OPTIONS,
            help="Optional. Choose not_supplied if the 1004MC data is not available.",
            key=_widget_key("market_trend_classification_input"),
        )

        st.text_area(
            "1004MC / trend note for valuation handoff (optional)",
            height=80,
            placeholder="Example: 1004MC indicates stable pricing over the last 12 months; use only as secondary support.",
            key=_widget_key("manual_1004mc_note_input"),
        )

        st.checkbox(
            "Auto-calculate annual/monthly trend from 1004MC median close prices when manual trend is left at 0.00",
            help=(
                "Uses Prior 7–12 Months median close price compared to Current–3 Months median close price. "
                "This is a support indicator only."
            ),
            key=_widget_key("auto_calc_1004mc_trend_checkbox"),
        )

        if st.button("Save 1004MC / Time-Trend Handoff", type="primary"):
            verified_1004mc = _collect_1004mc_from_widgets(parsed_or_existing)

            annual_market_change_percent = _safe_float(
                st.session_state.get(_widget_key("annual_market_change_percent_input"))
            )
            monthly_market_change_percent = _safe_float(
                st.session_state.get(_widget_key("monthly_market_change_percent_input"))
            )
            auto_calc = bool(st.session_state.get(_widget_key("auto_calc_1004mc_trend_checkbox")))

            if auto_calc and annual_market_change_percent == 0 and monthly_market_change_percent == 0:
                verified_1004mc = _calc_market_change_from_1004mc(verified_1004mc)

            save_path = _save_1004mc_to_session_and_disk(verified_1004mc)
            st.session_state["1004mc_pending_widget_load"] = True
            st.session_state["1004mc_message"] = {
                "type": "success",
                "text": f"1004MC / market-trend handoff saved to {save_path}",
            }
            st.rerun()

    saved_summary = st.session_state.get("one_hundred_four_mc_summary") or load_verified_1004mc() or None

    if saved_summary:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "1004MC Status",
            saved_summary.get("source_status", saved_summary.get("recommended_route", "verified")),
        )

        annual = saved_summary.get("annual_market_change_percent")
        monthly = saved_summary.get("monthly_market_change_percent")

        c2.metric("Annual Trend", _render_metric_value(annual, "%"))
        c3.metric("Monthly Trend", _render_metric_value(monthly, "%"))
        c4.metric("Trend Class", saved_summary.get("market_trend_classification", "not_supplied"))

        with st.expander("1004MC structured handoff", expanded=False):
            st.json(saved_summary)

        validation = saved_summary.get("validation")
        if validation:
            with st.expander("1004MC validation details", expanded=False):
                st.json(validation)
    else:
        st.info("1004MC is optional. You may proceed to Module 4 without it.")

    st.success("Proceed to Module 4 when the MLS preview and optional 1004MC handoff look correct.")

else:
    st.info("Upload and confirm the Comparable Sales / Valuation File before adding optional 1004MC evidence.")
