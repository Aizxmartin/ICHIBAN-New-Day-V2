from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


DEFAULT_REPORT_VERSION = "tarzan_valuation_analysis"

REPORT_VERSIONS: Dict[str, Dict[str, str]] = {
    "tarzan_valuation_analysis": {
        "label": "Tarzan Valuation Analysis",
        "purpose": (
            "The single active ICHIBAN report is Tarzan Valuation Analysis. "
            "BBC, After Review, and Retrospect remain paused until explicitly activated."
        ),
    },
}

LEGACY_REPORT_VERSION_ALIASES = {
    # Older names remain accepted only so stale session state or saved JSON
    # does not break the app. They never activate another report system.
    "combined": DEFAULT_REPORT_VERSION,
    "bbc_tarzan": DEFAULT_REPORT_VERSION,
    "tarzan_valuation_analysis_report": DEFAULT_REPORT_VERSION,
    "tarzan": DEFAULT_REPORT_VERSION,
    "seller_report_package_—_full_default": DEFAULT_REPORT_VERSION,
    "seller_report_package_full_default": DEFAULT_REPORT_VERSION,
    "seller_report_package_summary": DEFAULT_REPORT_VERSION,
    "internal_review_package": DEFAULT_REPORT_VERSION,
    "valuation_json_only": DEFAULT_REPORT_VERSION,
    "seller_story": DEFAULT_REPORT_VERSION,
    "bbc": DEFAULT_REPORT_VERSION,
    "bbc_seller_story": DEFAULT_REPORT_VERSION,
    "tarzan_supporting_detail": DEFAULT_REPORT_VERSION,
    "tarzan_agent_deep_dive": DEFAULT_REPORT_VERSION,
    "deep_dive": DEFAULT_REPORT_VERSION,
    "agent_deep_dive": DEFAULT_REPORT_VERSION,
    "valuation": DEFAULT_REPORT_VERSION,
    "valuation_only": DEFAULT_REPORT_VERSION,
    "after_active": DEFAULT_REPORT_VERSION,
    "after_active_review": DEFAULT_REPORT_VERSION,
    "manual": DEFAULT_REPORT_VERSION,
    "manually": DEFAULT_REPORT_VERSION,
    "manual_input": DEFAULT_REPORT_VERSION,
    "manual_mode": DEFAULT_REPORT_VERSION,
}

STATUS_COLUMNS = [
    "mls_status",
    "status",
    "standard_status",
    "standard status",
    "property_status",
]

ADDRESS_COLUMNS = [
    "address",
    "property_address",
    "property address",
    "full_address",
    "full address",
    "street_address",
    "street address",
]

PRICE_COLUMNS = [
    "current_price",
    "current price",
    "list_price",
    "list price",
    "original list price",
]

ORIGINAL_PRICE_COLUMNS = [
    "original_list_price",
    "original list price",
    "original_price",
    "original price",
]

PREVIOUS_PRICE_COLUMNS = [
    "previous_list_price",
    "previous list price",
    "previous_price",
    "previous price",
]

DIM_COLUMNS = [
    "days_in_mls",
    "days in mls",
    "dim",
    "dom",
    "cdom",
    "cumulative days on market",
]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().replace("#", " ").split())


def _clean_key(value: Any) -> str:
    return _clean_text(value).replace(" ", "_").replace("/", "_").replace("-", "_")


def _clean_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    text = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
    if not text or text.lower() in {"nan", "none", "null", "—"}:
        return None

    try:
        return float(text)
    except Exception:
        return None


def _find_column(
    df: Optional[pd.DataFrame],
    candidates: Iterable[str],
) -> Optional[str]:
    if df is None or df.empty:
        return None

    labels = [str(c).strip() for c in df.columns]
    normalized = {
        label.lower().replace(" ", "_"): label
        for label in labels
    }

    for candidate in candidates:
        key = str(candidate).strip().lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]

    for candidate in candidates:
        key = str(candidate).strip().lower().replace(" ", "_")
        for label in labels:
            normalized_label = label.lower().replace(" ", "_")
            if key in normalized_label:
                return label

    return None


def _status_counts_from_df(
    df: Optional[pd.DataFrame],
) -> Dict[str, int]:
    status_col = _find_column(df, STATUS_COLUMNS)

    if df is None or df.empty or status_col is None:
        return {}

    counts: Dict[str, int] = {}

    for value in df[status_col].dropna().tolist():
        status = _clean_text(value)
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1

    return counts


def _group_status_counts(
    status_counts: Dict[str, int],
) -> Dict[str, int]:
    grouped = {
        "active_records": 0,
        "coming_soon_records": 0,
        "pending_records": 0,
        "closed_records": 0,
        "withdrawn_expired_records": 0,
    }

    for status, count in (status_counts or {}).items():
        status_norm = _clean_text(status)

        if "coming soon" in status_norm:
            grouped["coming_soon_records"] += int(count)
        elif "active" in status_norm:
            grouped["active_records"] += int(count)
        elif "pending" in status_norm or "under contract" in status_norm:
            grouped["pending_records"] += int(count)
        elif (
            "closed" in status_norm
            or "sold" in status_norm
            or "settled" in status_norm
        ):
            grouped["closed_records"] += int(count)
        elif (
            "withdrawn" in status_norm
            or "expired" in status_norm
            or "cancel" in status_norm
        ):
            grouped["withdrawn_expired_records"] += int(count)

    return grouped


def _subject_address(
    subject_property: Dict[str, Any],
) -> str:
    for key in [
        "subject_address",
        "address",
        "property_address",
        "full_address",
        "street_address",
    ]:
        value = subject_property.get(key)
        if value:
            return _clean_text(value)

    return ""


def _row_text(row: pd.Series) -> str:
    return _clean_text(
        " ".join(
            str(v)
            for v in row.to_dict().values()
            if v not in (None, "")
        )
    )


def _matching_subject_row(
    subject_property: Dict[str, Any],
    df: Optional[pd.DataFrame],
) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None

    subject_address = _subject_address(subject_property)
    if not subject_address:
        return None

    address_col = _find_column(df, ADDRESS_COLUMNS)

    if address_col:
        for _, row in df.iterrows():
            row_address = _clean_text(row.get(address_col))
            if row_address and (
                subject_address in row_address
                or row_address in subject_address
            ):
                return row

    # Fallback for MLS exports that split the address into number/street columns.
    subject_tokens = [
        token
        for token in subject_address.split()
        if len(token) > 1
    ]

    if not subject_tokens:
        return None

    for _, row in df.iterrows():
        text = _row_text(row)
        hits = sum(
            1
            for token in subject_tokens
            if token in text
        )

        if hits >= min(3, len(subject_tokens)):
            return row

    return None


def _row_value(
    row: Optional[pd.Series],
    df: Optional[pd.DataFrame],
    candidates: Iterable[str],
) -> Any:
    if row is None:
        return None

    col = _find_column(df, candidates)
    if col is None:
        return None

    return row.get(col)


def _subject_status(
    subject_property: Dict[str, Any],
    df: Optional[pd.DataFrame],
) -> Optional[str]:
    for key in [
        "status",
        "subject_status",
        "mls_status",
        "property_status",
    ]:
        if subject_property.get(key):
            return _clean_text(subject_property.get(key))

    row = _matching_subject_row(subject_property, df)
    status = _row_value(row, df, STATUS_COLUMNS)

    return _clean_text(status) if status is not None else None


def _notes_indicate_current_market_activity(notes: Any) -> bool:
    """
    Detect current-market activity for Tarzan context only.

    Important:
    This function does not activate another report, overlay, or range policy.
    It exists only to preserve useful current-market context in the routing
    payload while Tarzan remains the single active report.
    """
    text = _clean_text(notes)

    triggers = [
        "already active",
        "active on the market",
        "currently active",
        "on the market",
        "price reduced",
        "price reduction",
        "no showing",
        "no showings",
        "not getting showings",
        "low showing",
        "weak showing",
        "stale",
        "withdrawn",
        "expired",
        "prior listingid",
        "prior listing id",
        "listingid",
        "relist",
        "re-listed",
        "listing history",
        "cumulative days",
    ]

    return any(trigger in text for trigger in triggers)


def _status_indicates_current_market_activity(
    status: Optional[str],
) -> bool:
    """
    Detect active-market status for Tarzan context only.

    Closed/sold records are not treated as current-market status signals.
    Detection never changes the active report version.
    """
    text = _clean_text(status)

    if not text:
        return False

    if "closed" in text or "sold" in text:
        return False

    trigger_fragments = [
        "active",
        "coming soon",
        "pending",
        "under contract",
        "withdrawn",
        "expired",
        "cancel",
        "hold",
    ]

    return any(
        fragment in text
        for fragment in trigger_fragments
    )


def resolve_requested_report_version(
    requested_report_version: Optional[str],
) -> str:
    """
    Resolve every legacy report name to the single active Tarzan valuation package.

    Important rule:
    ICHIBAN currently exposes only Tarzan Valuation Analysis.
    Legacy report names are accepted only for compatibility with stale session
    state or saved JSON. Paused report systems must not alter Tarzan routing.
    Manual remains an input mode only.
    """
    if not requested_report_version:
        return DEFAULT_REPORT_VERSION

    key = _clean_key(requested_report_version)
    return LEGACY_REPORT_VERSION_ALIASES.get(
        key,
        DEFAULT_REPORT_VERSION,
    )


def summarize_market_file_for_routing(
    market_df: Optional[pd.DataFrame] = None,
    existing_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Summarize status counts for Tarzan market context.

    Closed plus active/pending records may coexist in one MLS file. Their presence
    is descriptive evidence only and does not activate a separate report mode.
    """
    status_counts = _status_counts_from_df(market_df)

    if not status_counts and existing_summary:
        existing_status_counts = (
            existing_summary.get("status_counts")
            or existing_summary.get("counts")
            or {}
        )

        if isinstance(existing_status_counts, dict):
            status_counts = {
                str(k): int(v)
                for k, v in existing_status_counts.items()
                if str(v).replace(".", "", 1).isdigit()
            }

    grouped = _group_status_counts(status_counts)
    records = 0 if market_df is None else int(len(market_df))

    if existing_summary:
        records = records or int(
            existing_summary.get("records")
            or existing_summary.get("rows")
            or 0
        )

        for key in grouped:
            grouped[key] = (
                grouped[key]
                or int(existing_summary.get(key) or 0)
            )

    same_file_supports_competition = (
        grouped["closed_records"] > 0
        and (
            grouped["active_records"]
            + grouped["coming_soon_records"]
            + grouped["pending_records"]
        ) > 0
    )

    return {
        "records": records,
        "status_counts": status_counts,
        **grouped,
        "competition_file_inferred_from_same_file": (
            same_file_supports_competition
        ),
    }


def resolve_report_routing(
    *,
    requested_report_version: Optional[str] = None,
    input_mode: Optional[str] = None,
    subject_property: Optional[Dict[str, Any]] = None,
    market_df: Optional[pd.DataFrame] = None,
    market_summary: Optional[Dict[str, Any]] = None,
    showing_activity_notes: Any = None,
) -> Dict[str, Any]:
    """
    Resolve report routing under the Tarzan-first scope lock.

    Rules:
    - Tarzan Valuation Analysis is the only active report.
    - Manual is an input mode, never a report version.
    - Current listing activity may be detected and preserved as market context.
    - Current listing activity must not activate another report, overlay, or
      alternate range policy.
    - Legacy return keys are preserved where practical so older callers do not
      fail while the application transitions to the Tarzan-first architecture.
    """
    subject_property = subject_property or {}

    resolved_report_version = resolve_requested_report_version(
        requested_report_version
    )

    input_mode_clean = (
        _clean_key(input_mode or "hybrid")
        or "hybrid"
    )

    status_counts_summary = summarize_market_file_for_routing(
        market_df,
        market_summary,
    )

    subject_row = _matching_subject_row(
        subject_property,
        market_df,
    )

    status = _subject_status(
        subject_property,
        market_df,
    )

    current_price = _clean_number(
        _row_value(
            subject_row,
            market_df,
            PRICE_COLUMNS,
        )
    )

    original_price = _clean_number(
        _row_value(
            subject_row,
            market_df,
            ORIGINAL_PRICE_COLUMNS,
        )
    )

    previous_price = _clean_number(
        _row_value(
            subject_row,
            market_df,
            PREVIOUS_PRICE_COLUMNS,
        )
    )

    dim = _clean_number(
        _row_value(
            subject_row,
            market_df,
            DIM_COLUMNS,
        )
    )

    if current_price is None:
        current_price = _clean_number(
            subject_property.get("current_price")
            or subject_property.get("list_price")
            or subject_property.get("current_list_price")
        )

    if original_price is None:
        original_price = _clean_number(
            subject_property.get("original_list_price")
            or subject_property.get("original_price")
        )

    if previous_price is None:
        previous_price = _clean_number(
            subject_property.get("previous_list_price")
            or subject_property.get("previous_price")
        )

    if dim is None:
        dim = _clean_number(
            subject_property.get("days_in_mls")
            or subject_property.get("dim")
            or subject_property.get("dom")
        )

    subject_status_trigger = (
        _status_indicates_current_market_activity(status)
    )

    notes_trigger = (
        _notes_indicate_current_market_activity(
            showing_activity_notes
        )
    )

    current_market_context_detected = (
        subject_status_trigger
        or notes_trigger
    )

    # Compatibility field retained intentionally.
    # Tarzan-first scope lock prevents any alternate overlay from activating.
    after_active_overlay = False

    price_reduction_detected = bool(
        original_price
        and current_price
        and current_price < original_price
    )

    warnings: List[str] = []

    if _clean_key(requested_report_version) in {
        "manual",
        "manually",
        "manual_input",
        "manual_mode",
    }:
        warnings.append(
            "Manual was treated as input mode only; "
            "report version remained tarzan_valuation_analysis."
        )

    if (
        requested_report_version
        and resolved_report_version == DEFAULT_REPORT_VERSION
        and _clean_key(requested_report_version)
        != DEFAULT_REPORT_VERSION
    ):
        warnings.append(
            "A legacy report name was supplied and normalized to "
            "Tarzan Valuation Analysis under the current scope lock."
        )

    if status_counts_summary[
        "competition_file_inferred_from_same_file"
    ]:
        warnings.append(
            "The MLS file contains closed plus active/pending evidence; "
            "the same file may support Tarzan valuation evidence and "
            "current competition context."
        )

    if current_market_context_detected:
        warnings.append(
            "Current listing activity was detected and retained as "
            "Tarzan market context only; no alternate report routing "
            "or overlay was activated."
        )

    if (
        subject_row is None
        and market_df is not None
        and not market_df.empty
    ):
        warnings.append(
            "The subject row was not matched inside the MLS file. "
            "Any supplied subject status or field notes remain context only."
        )

    range_policy = [
        "Closed-Comp Supported Range",
        "Current Competition Range",
        "Recommended Seller Position",
    ]

    return {
        "routing_version": (
            "report_routing_v20_5_4G_tarzan_scope_lock"
        ),
        "requested_report_version": (
            requested_report_version
            or DEFAULT_REPORT_VERSION
        ),
        "resolved_report_version": (
            resolved_report_version
        ),
        "resolved_report_label": (
            REPORT_VERSIONS[DEFAULT_REPORT_VERSION]["label"]
        ),
        "default_report_version": (
            DEFAULT_REPORT_VERSION
        ),
        "input_mode": input_mode_clean,
        "manual_is_input_mode_only": True,

        # Compatibility key retained. It is intentionally always False
        # under the current Tarzan-first scope lock.
        "after_active_overlay": after_active_overlay,

        # Compatibility/context payload retained without activating
        # alternate report behavior.
        "after_active_reason": {
            "subject_status": status,
            "subject_status_trigger": subject_status_trigger,
            "notes_trigger": notes_trigger,
            "current_market_context_detected": (
                current_market_context_detected
            ),
            "overlay_activated": False,
        },

        "subject_match_found_in_market_file": (
            subject_row is not None
        ),

        "subject_market_snapshot": {
            "status": status,
            "current_price": current_price,
            "original_price": original_price,
            "previous_price": previous_price,
            "dim": dim,
            "price_reduction_detected": (
                price_reduction_detected
            ),
        },

        "market_file_summary": (
            status_counts_summary
        ),

        "range_policy": (
            range_policy
        ),

        "warnings": warnings,
    }
