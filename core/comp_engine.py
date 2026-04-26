from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class CompEngineResult:
    closed_rows: pd.DataFrame
    priced_closed_rows: pd.DataFrame
    candidate_comps: pd.DataFrame
    selected_comps: pd.DataFrame
    selected_comp_preview: pd.DataFrame
    recommended_low: Optional[float]
    recommended_high: Optional[float]
    average_ppsf: Optional[float]
    median_effective_price: Optional[float]
    debug: Dict[str, Any]


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def _find_col(df: pd.DataFrame, preferred: str) -> Optional[str]:
    if preferred in df.columns:
        return preferred

    target = preferred.lower().replace(" ", "_")
    for col in df.columns:
        normalized = str(col).strip().lower().replace(" ", "_")
        if normalized == target:
            return col

    return None


def _get_subject_ag_sqft(subject_profile: Dict[str, Any]) -> Optional[float]:
    candidates = [
        "above_grade_sqft",
        "above_grade_finished_area",
        "ag_sqft",
        "finished_sqft",
    ]

    for key in candidates:
        value = subject_profile.get(key)
        if value not in (None, ""):
            try:
                return float(str(value).replace(",", ""))
            except Exception:
                pass

    for nested_key in ["subject_data", "subject_profile", "normalized_subject"]:
        nested = subject_profile.get(nested_key)
        if isinstance(nested, dict):
            val = _get_subject_ag_sqft(nested)
            if val:
                return val

    return None


def run_comp_engine(market_df: pd.DataFrame, subject_profile: Dict[str, Any]) -> CompEngineResult:
    df = market_df.copy()

    status_col = _find_col(df, "mls_status")
    net_col = _find_col(df, "net_close_price")
    close_col = _find_col(df, "close_price")
    ag_col = _find_col(df, "above_grade_sqft")

    debug: Dict[str, Any] = {
        "input_rows": int(len(df)),
        "input_columns": list(map(str, df.columns)),
        "status_column_used": status_col,
        "net_close_price_column_used": net_col,
        "close_price_column_used": close_col,
        "above_grade_sqft_column_used": ag_col,
        "status_value_counts": {},
        "subject_above_grade_sqft": None,
        "ag_band_low": None,
        "ag_band_high": None,
    }

    if status_col is None:
        empty = df.iloc[0:0].copy()
        debug["reason"] = "No mls_status column found."
        return CompEngineResult(
            closed_rows=empty,
            priced_closed_rows=empty,
            candidate_comps=empty,
            selected_comps=empty,
            selected_comp_preview=empty,
            recommended_low=None,
            recommended_high=None,
            average_ppsf=None,
            median_effective_price=None,
            debug=debug,
        )

    # --- STATUS FILTER ---
    status_normalized = df[status_col].astype(str).str.strip().str.lower()
    debug["status_value_counts"] = status_normalized.value_counts(dropna=False).head(20).to_dict()

    closed = df.loc[status_normalized.eq("closed")].copy()

    # --- PRICE CLEANING ---
    if net_col is not None:
        closed["_net_close_price_num"] = _to_number(closed[net_col])
    else:
        closed["_net_close_price_num"] = pd.NA

    if close_col is not None:
        closed["_close_price_num"] = _to_number(closed[close_col])
    else:
        closed["_close_price_num"] = pd.NA

    closed["effective_sale_price"] = closed["_net_close_price_num"].fillna(
        closed["_close_price_num"]
    )

    priced_closed = closed.loc[
        pd.to_numeric(closed["effective_sale_price"], errors="coerce").fillna(0) > 0
    ].copy()

    subject_ag = _get_subject_ag_sqft(subject_profile)
    debug["subject_above_grade_sqft"] = subject_ag

    candidates = priced_closed.copy()

    # --- SIZE FILTER FIRST ---
    if subject_ag and ag_col is not None:
        ag_low = subject_ag * 0.85
        ag_high = subject_ag * 1.10

        debug["ag_band_low"] = ag_low
        debug["ag_band_high"] = ag_high

        candidates["_ag_sqft_num"] = _to_number(candidates[ag_col])
        candidates = candidates[candidates["_ag_sqft_num"].notna()].copy()

        candidates = candidates.loc[
            candidates["_ag_sqft_num"].between(ag_low, ag_high, inclusive="both")
        ].copy()

        candidates["_ag_diff_abs"] = (candidates["_ag_sqft_num"] - subject_ag).abs()

        candidates = candidates.sort_values(
            ["_ag_diff_abs", "effective_sale_price"],
            ascending=[True, True],
        )

        # --- OUTLIER FILTER AFTER SIZE FILTER ---
        prices = pd.to_numeric(candidates["effective_sale_price"], errors="coerce").dropna()

        if not prices.empty and len(prices) >= 6:
            low = prices.quantile(0.10)
            high = prices.quantile(0.90)

            candidates = candidates.loc[
                candidates["effective_sale_price"].between(low, high, inclusive="both")
            ].copy()

            debug["outlier_low"] = float(low)
            debug["outlier_high"] = float(high)
            debug["post_outlier_count"] = int(len(candidates))
        else:
            debug["outlier_low"] = None
            debug["outlier_high"] = None
            debug["post_outlier_count"] = int(len(candidates))
            debug["outlier_note"] = "Skipped outlier filter because candidate pool is small."

    else:
        debug["reason_no_ag_filter"] = "AG sqft missing; skipping size filter."

    # --- FINAL SELECTION ---
    selected = candidates.head(6).copy()

    if not selected.empty:
        prices = pd.to_numeric(selected["effective_sale_price"], errors="coerce").dropna()

        if ag_col is not None:
            selected["_ag_for_ppsf"] = _to_number(selected[ag_col])
            selected["effective_ppsf"] = (
                selected["effective_sale_price"]
                / selected["_ag_for_ppsf"].replace(0, pd.NA)
            )
        else:
            selected["effective_ppsf"] = pd.NA

        median_effective_price = float(prices.median()) if not prices.empty else None

        recommended_low = float(prices.min()) if not prices.empty else None
        recommended_high = float(prices.max()) if not prices.empty else None

        average_ppsf = float(
            pd.to_numeric(selected["effective_ppsf"], errors="coerce").mean()
        )

    else:
        recommended_low = None
        recommended_high = None
        average_ppsf = None
        median_effective_price = None

    preview_cols = [
        c for c in [
            "street_number",
            "street_name",
            "mls_status",
            "above_grade_sqft",
            "beds",
            "baths",
            "year_built",
            "days_in_mls",
            "net_close_price",
            "close_price",
            "effective_sale_price",
            "effective_ppsf",
        ]
        if c in selected.columns
    ]

    selected_comp_preview = selected[preview_cols].copy() if preview_cols else selected.copy()

    return CompEngineResult(
        closed_rows=closed,
        priced_closed_rows=priced_closed,
        candidate_comps=candidates,
        selected_comps=selected,
        selected_comp_preview=selected_comp_preview,
        recommended_low=recommended_low,
        recommended_high=recommended_high,
        average_ppsf=average_ppsf,
        median_effective_price=median_effective_price,
        debug=debug,
    )