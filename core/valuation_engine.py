from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re

import pandas as pd


ENGINE_VERSION = "pre_api_baseline_valuation_engine_v1"


COLUMN_ALIASES = {
    "status": [
        "status",
        "mlsstatus",
        "mls status",
        "standardstatus",
        "standard status",
        "property status",
    ],
    "close_price": [
        "closeprice",
        "close price",
        "closedprice",
        "closed price",
        "soldprice",
        "sold price",
        "saleprice",
        "sale price",
    ],
    "list_price": [
        "listprice",
        "list price",
        "currentprice",
        "current price",
        "originallistprice",
        "original list price",
    ],
    "concessions": [
        "concessions",
        "sellerconcessions",
        "seller concessions",
        "closingcosts",
        "closing costs",
        "sellerpaidclosingcosts",
        "seller paid closing costs",
    ],
    "above_grade_sqft": [
        "abovegradefinishedarea",
        "above grade finished area",
        "abovegradefinishedsqft",
        "above grade finished sqft",
        "abovegradefinisheddarea",
        "above grade",
        "abovegradesqft",
        "above grade sqft",
        "buildingareatotal",
        "building area total",
        "livingarea",
        "living area",
        "sqft",
        "squarefeet",
        "square feet",
    ],
    "basement_sqft": [
        "belowgradearea",
        "below grade area",
        "basementsqft",
        "basement sqft",
        "basement sf",
        "belowgradesqft",
        "below grade sqft",
    ],
    "finished_basement_sqft": [
        "belowgradefinishedarea",
        "below grade finished area",
        "finishedbasementsqft",
        "finished basement sqft",
        "finished basement sf",
    ],
    "year_built": [
        "yearbuilt",
        "year built",
    ],
    "beds": [
        "beds",
        "bedrooms",
        "bedroomstotal",
        "bedrooms total",
    ],
    "baths": [
        "baths",
        "bathrooms",
        "bathroomstotal",
        "bathrooms total",
        "totalbaths",
        "total baths",
    ],
    "days_in_mls": [
        "daysinmls",
        "days in mls",
        "dim",
        "dom",
        "daysonmarket",
        "days on market",
        "cumulativedaysonmarket",
        "cumulative days on market",
    ],
    "close_date": [
        "closedate",
        "close date",
        "sold date",
        "solddate",
        "closingdate",
        "closing date",
    ],
    "address": [
        "address",
        "fulladdress",
        "full address",
        "unparsedaddress",
        "unparsed address",
        "propertyaddress",
        "property address",
        "streetaddress",
        "street address",
    ],
    "street_number": [
        "streetnumbernumeric",
        "street number numeric",
        "streetnumber",
        "street number",
    ],
    "street_name": [
        "streetname",
        "street name",
    ],
    "city": [
        "city",
    ],
    "subdivision": [
        "subdivision",
        "subdivisionname",
        "subdivision name",
    ],
}


def run_valuation_engine(
    subject_profile: Dict[str, Any],
    market_data: Any,
    one_hundred_four_mc_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    ICHIBAN INSIGHT baseline valuation engine.

    This is a pre-API deterministic starter engine. It is designed to prove that:

        verified_subject.json
        + normalized MLS market data
        + verified_1004mc.json

    can flow into a valuation package.

    This is not yet the final proprietary adjustment engine. It creates a clean,
    defensible baseline using closed comps, size filtering, PPSF support, AVM
    support, and 1004MC trend evidence.
    """

    one_hundred_four_mc_summary = one_hundred_four_mc_summary or {}

    warnings: List[str] = []
    notes: List[str] = []

    df = _as_dataframe(market_data)

    if df.empty:
        return {
            "engine_version": ENGINE_VERSION,
            "engine_status": "blocked",
            "reason": "Market data is empty or could not be converted to a DataFrame.",
            "subject_summary": _subject_summary(subject_profile),
            "warnings": warnings,
        }

    subject_summary = _subject_summary(subject_profile)

    subject_above_grade = _to_number(
        subject_profile.get("above_grade_sqft")
        or subject_profile.get("building_sqft")
    )

    if not subject_above_grade:
        warnings.append(
            "Subject above-grade square footage is missing. Comp PPSF valuation will be weaker."
        )

    column_map = _detect_columns(df)

    prepared = _prepare_market_dataframe(
        df=df,
        column_map=column_map,
        subject_above_grade=subject_above_grade,
        warnings=warnings,
    )

    closed_df = prepared["closed_df"]
    comp_df = prepared["comp_df"]
    notes.extend(prepared["notes"])

    if comp_df.empty:
        return {
            "engine_version": ENGINE_VERSION,
            "engine_status": "blocked",
            "reason": "No usable closed comparable sales were available after preparation.",
            "subject_summary": subject_summary,
            "column_map": column_map,
            "market_rows_loaded": int(len(df)),
            "warnings": warnings,
            "notes": notes,
        }

    comp_stats = _calculate_comp_stats(
        comp_df=comp_df,
        subject_above_grade=subject_above_grade,
        one_hundred_four_mc_summary=one_hundred_four_mc_summary,
    )

    avm_summary = _calculate_avm_summary(subject_profile)

    recommended_range = _calculate_recommended_range(
        comp_stats=comp_stats,
        avm_summary=avm_summary,
        warnings=warnings,
    )

    market_conditions_summary = _summarize_1004mc(one_hundred_four_mc_summary)

    comp_records = _build_comp_records(comp_df, column_map)

    result = {
        "engine_version": ENGINE_VERSION,
        "engine_status": "success",
        "engine_scope": "baseline_pre_api_valuation",
        "important_note": (
            "This is the first connected valuation engine. It is intended to verify "
            "the full intake-to-valuation pipeline. Final ICHIBAN adjustment logic can "
            "be layered on top after this baseline engine is stable."
        ),
        "subject_summary": subject_summary,
        "market_rows_loaded": int(len(df)),
        "closed_rows_available": int(len(closed_df)),
        "comp_rows_used": int(len(comp_df)),
        "column_map": column_map,
        "comp_filtering": {
            "subject_above_grade_sqft": subject_above_grade,
            "target_above_grade_min_85pct": (
                round(subject_above_grade * 0.85, 2) if subject_above_grade else None
            ),
            "target_above_grade_max_110pct": (
                round(subject_above_grade * 1.10, 2) if subject_above_grade else None
            ),
            "filter_notes": notes,
        },
        "comp_statistics": comp_stats,
        "avm_summary": avm_summary,
        "market_conditions_1004mc": market_conditions_summary,
        "recommended_range": recommended_range,
        "comp_records_used": comp_records,
        "warnings": warnings,
        "notes": notes,
    }

    return _json_safe(result)


# ---------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------

def _as_dataframe(market_data: Any) -> pd.DataFrame:
    if market_data is None:
        return pd.DataFrame()

    if isinstance(market_data, pd.DataFrame):
        return market_data.copy()

    if isinstance(market_data, list):
        return pd.DataFrame(market_data)

    if isinstance(market_data, dict):
        try:
            return pd.DataFrame(market_data)
        except Exception:
            return pd.DataFrame([market_data])

    return pd.DataFrame()


def _detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    detected: Dict[str, Optional[str]] = {}

    normalized_columns = {
        _normalize_column_name(column): column
        for column in df.columns
    }

    for logical_name, aliases in COLUMN_ALIASES.items():
        found = None

        for alias in aliases:
            normalized_alias = _normalize_column_name(alias)

            if normalized_alias in normalized_columns:
                found = normalized_columns[normalized_alias]
                break

        if found is None:
            # Soft contains fallback.
            for normalized_column, original_column in normalized_columns.items():
                if any(_normalize_column_name(alias) in normalized_column for alias in aliases):
                    found = original_column
                    break

        detected[logical_name] = found

    return detected


def _prepare_market_dataframe(
    df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
    subject_above_grade: Optional[float],
    warnings: List[str],
) -> Dict[str, Any]:
    working = df.copy()
    notes: List[str] = []

    close_col = column_map.get("close_price")
    list_col = column_map.get("list_price")
    concessions_col = column_map.get("concessions")
    ag_col = column_map.get("above_grade_sqft")
    status_col = column_map.get("status")

    if close_col is None:
        warnings.append("Close Price column was not detected. Valuation may be blocked.")
        return {
            "closed_df": pd.DataFrame(),
            "comp_df": pd.DataFrame(),
            "notes": notes,
        }

    working["_close_price"] = working[close_col].apply(_to_number)

    if list_col:
        working["_list_price"] = working[list_col].apply(_to_number)
    else:
        working["_list_price"] = None

    if concessions_col:
        working["_concessions"] = working[concessions_col].apply(_to_number).fillna(0)
    else:
        working["_concessions"] = 0
        notes.append("No concessions column detected; net price equals close price.")

    if ag_col:
        working["_above_grade_sqft"] = working[ag_col].apply(_to_number)
    else:
        working["_above_grade_sqft"] = None
        warnings.append("Above-grade square footage column was not detected.")

    working["_net_price"] = working["_close_price"] - working["_concessions"]

    working = working[
        working["_close_price"].notna()
        & (working["_close_price"] > 0)
        & working["_net_price"].notna()
        & (working["_net_price"] > 0)
    ].copy()

    if working.empty:
        return {
            "closed_df": pd.DataFrame(),
            "comp_df": pd.DataFrame(),
            "notes": notes,
        }

    if status_col:
        status_text = working[status_col].astype(str).str.lower()
        closed_mask = (
            status_text.str.contains("closed")
            | status_text.str.contains("sold")
            | status_text.str.contains("settled")
        )

        closed_df = working[closed_mask].copy()

        if closed_df.empty:
            closed_df = working.copy()
            warnings.append(
                "No rows clearly marked Closed/Sold were detected; using rows with usable close prices."
            )
    else:
        closed_df = working.copy()
        warnings.append(
            "MLS status column was not detected; using rows with usable close prices."
        )

    comp_df = closed_df.copy()

    if subject_above_grade and ag_col:
        low = subject_above_grade * 0.85
        high = subject_above_grade * 1.10

        size_filtered = comp_df[
            comp_df["_above_grade_sqft"].notna()
            & (comp_df["_above_grade_sqft"] >= low)
            & (comp_df["_above_grade_sqft"] <= high)
        ].copy()

        if len(size_filtered) >= 3:
            comp_df = size_filtered
            notes.append(
                f"Applied 85% to 110% above-grade size filter: {round(low)} to {round(high)} sqft."
            )
        elif len(size_filtered) > 0:
            comp_df = size_filtered
            warnings.append(
                f"Only {len(size_filtered)} comps remained after the 85% to 110% size filter."
            )
        else:
            warnings.append(
                "No comps remained after the 85% to 110% above-grade size filter; using all closed comps."
            )
    else:
        notes.append(
            "Above-grade size filter was not applied because subject or comp square footage was missing."
        )

    if ag_col and "_above_grade_sqft" in comp_df.columns:
        comp_df["_net_ppsf"] = comp_df.apply(
            lambda row: (
                row["_net_price"] / row["_above_grade_sqft"]
                if row["_above_grade_sqft"] and row["_above_grade_sqft"] > 0
                else None
            ),
            axis=1,
        )
    else:
        comp_df["_net_ppsf"] = None

    if subject_above_grade:
        comp_df["_subject_size_ppsf_estimate"] = comp_df["_net_ppsf"].apply(
            lambda ppsf: ppsf * subject_above_grade if ppsf and ppsf > 0 else None
        )
    else:
        comp_df["_subject_size_ppsf_estimate"] = None

    comp_df = comp_df.sort_values(
        by=["_subject_size_ppsf_estimate", "_net_price"],
        na_position="last",
    ).copy()

    return {
        "closed_df": closed_df,
        "comp_df": comp_df,
        "notes": notes,
    }


# ---------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------

def _calculate_comp_stats(
    comp_df: pd.DataFrame,
    subject_above_grade: Optional[float],
    one_hundred_four_mc_summary: Dict[str, Any],
) -> Dict[str, Any]:
    net_prices = _clean_numeric_list(comp_df["_net_price"].tolist())
    ppsf_values = _clean_numeric_list(comp_df["_net_ppsf"].tolist())
    subject_size_estimates = _clean_numeric_list(
        comp_df["_subject_size_ppsf_estimate"].tolist()
    )

    median_net_price = _median(net_prices)
    average_net_price = _average(net_prices)

    median_ppsf = _median(ppsf_values)
    average_ppsf = _average(ppsf_values)

    if subject_size_estimates:
        median_subject_size_estimate = _median(subject_size_estimates)
        average_subject_size_estimate = _average(subject_size_estimates)
    elif subject_above_grade and median_ppsf:
        median_subject_size_estimate = median_ppsf * subject_above_grade
        average_subject_size_estimate = average_ppsf * subject_above_grade if average_ppsf else None
    else:
        median_subject_size_estimate = median_net_price
        average_subject_size_estimate = average_net_price

    return {
        "median_net_price": _round_money(median_net_price),
        "average_net_price": _round_money(average_net_price),
        "lowest_net_price": _round_money(min(net_prices)) if net_prices else None,
        "highest_net_price": _round_money(max(net_prices)) if net_prices else None,
        "median_net_ppsf": round(median_ppsf, 2) if median_ppsf else None,
        "average_net_ppsf": round(average_ppsf, 2) if average_ppsf else None,
        "median_subject_size_ppsf_estimate": _round_money(median_subject_size_estimate),
        "average_subject_size_ppsf_estimate": _round_money(average_subject_size_estimate),
        "comp_count": int(len(comp_df)),
        "time_trend_context": {
            "annual_market_change_percent": one_hundred_four_mc_summary.get(
                "annual_market_change_percent"
            ),
            "monthly_market_change_percent": one_hundred_four_mc_summary.get(
                "monthly_market_change_percent"
            ),
            "market_trend_classification": one_hundred_four_mc_summary.get(
                "market_trend_classification"
            ),
            "time_adjustment_applied_in_this_engine": False,
            "note": (
                "1004MC trend is loaded as support context. Time adjustments are not "
                "automatically applied in this baseline engine."
            ),
        },
    }


def _calculate_avm_summary(subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    values = []

    real_avm = _to_number(subject_profile.get("real_avm"))
    real_low = _to_number(subject_profile.get("real_avm_range_low"))
    real_high = _to_number(subject_profile.get("real_avm_range_high"))
    zillow = _to_number(subject_profile.get("zillow_estimate"))
    redfin = _to_number(subject_profile.get("redfin_estimate"))

    if real_avm:
        values.append(("RealAVM", real_avm))
    if zillow:
        values.append(("Zillow", zillow))
    if redfin:
        values.append(("Redfin", redfin))

    numeric_values = [value for _, value in values]

    return {
        "real_avm": _round_money(real_avm),
        "real_avm_range_low": _round_money(real_low),
        "real_avm_range_high": _round_money(real_high),
        "zillow_estimate": _round_money(zillow),
        "redfin_estimate": _round_money(redfin),
        "online_estimate_sources_used": [name for name, _value in values],
        "online_estimate_average": _round_money(_average(numeric_values)),
        "online_estimate_low": _round_money(min(numeric_values)) if numeric_values else None,
        "online_estimate_high": _round_money(max(numeric_values)) if numeric_values else None,
    }


def _calculate_recommended_range(
    comp_stats: Dict[str, Any],
    avm_summary: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    comp_anchor = comp_stats.get("median_subject_size_ppsf_estimate")
    if comp_anchor is None:
        comp_anchor = comp_stats.get("median_net_price")

    if comp_anchor is None:
        warnings.append("No comp anchor was available for recommended range.")
        return {
            "range_low": None,
            "range_high": None,
            "range_width": None,
            "anchor_value": None,
            "method": "not_available",
        }

    anchor = float(comp_anchor)

    # Seller-facing recommendation target: generally keep spread around $50K.
    low = _round_to_nearest(anchor - 25_000, 5_000)
    high = _round_to_nearest(anchor + 25_000, 5_000)

    if high <= low:
        high = low + 50_000

    return {
        "range_low": int(low),
        "range_high": int(high),
        "range_width": int(high - low),
        "anchor_value": int(_round_to_nearest(anchor, 5_000)),
        "method": (
            "Baseline comp-based range using median subject-size PPSF estimate. "
            "AVMs are retained as support context, not the primary valuation anchor."
        ),
        "avm_support_average": avm_summary.get("online_estimate_average"),
    }


def _summarize_1004mc(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "is_supplied": bool(
            summary.get("is_supplied")
            or summary.get("recommended_route") == "parsed_1004mc_coordinate_table"
            or summary.get("current_3_sales") is not None
        ),
        "source_status": summary.get("source_status") or summary.get("recommended_route"),
        "parser_confidence": summary.get("parser_confidence"),
        "annual_market_change_percent": summary.get("annual_market_change_percent"),
        "monthly_market_change_percent": summary.get("monthly_market_change_percent"),
        "market_trend_classification": summary.get("market_trend_classification"),
        "current_3": {
            "sales": summary.get("current_3_sales"),
            "absorption_rate": summary.get("current_3_absorption_rate"),
            "active_listings": summary.get("current_3_active_listings"),
            "months_supply": summary.get("current_3_months_supply"),
            "median_close_price": summary.get("current_3_median_close_price"),
            "median_sales_dim": summary.get("current_3_median_sales_dim"),
        },
        "prior_4_6": {
            "sales": summary.get("prior_4_6_sales"),
            "absorption_rate": summary.get("prior_4_6_absorption_rate"),
            "active_listings": summary.get("prior_4_6_active_listings"),
            "months_supply": summary.get("prior_4_6_months_supply"),
            "median_close_price": summary.get("prior_4_6_median_close_price"),
            "median_sales_dim": summary.get("prior_4_6_median_sales_dim"),
        },
        "prior_7_12": {
            "sales": summary.get("prior_7_12_sales"),
            "absorption_rate": summary.get("prior_7_12_absorption_rate"),
            "active_listings": summary.get("prior_7_12_active_listings"),
            "months_supply": summary.get("prior_7_12_months_supply"),
            "median_close_price": summary.get("prior_7_12_median_close_price"),
            "median_sales_dim": summary.get("prior_7_12_median_sales_dim"),
        },
        "validation": summary.get("validation"),
    }


# ---------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------

def _subject_summary(subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "subject_address": subject_profile.get("subject_address"),
        "above_grade_sqft": subject_profile.get("above_grade_sqft"),
        "basement_sqft": subject_profile.get("basement_sqft"),
        "finished_basement_sqft": subject_profile.get("finished_basement_sqft"),
        "property_type": subject_profile.get("property_type"),
        "property_subtype": subject_profile.get("property_subtype"),
        "beds": subject_profile.get("beds"),
        "baths": subject_profile.get("baths"),
        "year_built": subject_profile.get("year_built"),
        "lot_sqft": subject_profile.get("lot_sqft"),
        "neighborhood_name": subject_profile.get("neighborhood_name"),
        "subdivision": subject_profile.get("subdivision"),
        "zoning": subject_profile.get("zoning"),
        "real_avm": subject_profile.get("real_avm"),
        "real_avm_range_low": subject_profile.get("real_avm_range_low"),
        "real_avm_range_high": subject_profile.get("real_avm_range_high"),
    }


def _build_comp_records(
    comp_df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    for _idx, row in comp_df.head(25).iterrows():
        address = _row_address(row, column_map)

        record = {
            "address": address,
            "status": _row_value(row, column_map.get("status")),
            "close_price": _round_money(row.get("_close_price")),
            "concessions": _round_money(row.get("_concessions")),
            "net_price": _round_money(row.get("_net_price")),
            "above_grade_sqft": _round_number(row.get("_above_grade_sqft")),
            "net_ppsf": _round_number(row.get("_net_ppsf"), decimals=2),
            "subject_size_ppsf_estimate": _round_money(
                row.get("_subject_size_ppsf_estimate")
            ),
            "days_in_mls": _row_value(row, column_map.get("days_in_mls")),
            "close_date": _row_value(row, column_map.get("close_date")),
            "year_built": _row_value(row, column_map.get("year_built")),
            "beds": _row_value(row, column_map.get("beds")),
            "baths": _row_value(row, column_map.get("baths")),
            "subdivision": _row_value(row, column_map.get("subdivision")),
        }

        records.append(_json_safe(record))

    return records


def _row_address(row: pd.Series, column_map: Dict[str, Optional[str]]) -> Optional[str]:
    address_col = column_map.get("address")
    if address_col and pd.notna(row.get(address_col)):
        return str(row.get(address_col))

    street_number_col = column_map.get("street_number")
    street_name_col = column_map.get("street_name")
    city_col = column_map.get("city")

    parts = []

    for col in [street_number_col, street_name_col, city_col]:
        if col and pd.notna(row.get(col)):
            parts.append(str(row.get(col)))

    return " ".join(parts).strip() or None


def _row_value(row: pd.Series, column: Optional[str]) -> Any:
    if not column:
        return None

    value = row.get(column)
    return None if _is_missing(value) else value


# ---------------------------------------------------------------------
# Generic utilities
# ---------------------------------------------------------------------

def _normalize_column_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _to_number(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None

    if isinstance(value, (int, float)):
        if math.isnan(value) if isinstance(value, float) else False:
            return None
        return float(value)

    cleaned = str(value)
    cleaned = cleaned.replace("$", "")
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("%", "")
    cleaned = cleaned.strip()

    if cleaned in {"", "-", "None", "nan", "NaN", "NULL"}:
        return None

    try:
        return float(cleaned)
    except Exception:
        return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    return False


def _clean_numeric_list(values: List[Any]) -> List[float]:
    output = []

    for value in values:
        number = _to_number(value)
        if number is not None and number > 0:
            output.append(float(number))

    return output


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None

    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2

    if n % 2 == 1:
        return sorted_values[mid]

    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def _average(values: List[float]) -> Optional[float]:
    if not values:
        return None

    return sum(values) / len(values)


def _round_money(value: Any) -> Optional[int]:
    number = _to_number(value)

    if number is None:
        return None

    return int(round(number))


def _round_number(value: Any, decimals: int = 0) -> Optional[float]:
    number = _to_number(value)

    if number is None:
        return None

    return round(number, decimals)


def _round_to_nearest(value: float, nearest: int) -> int:
    return int(round(value / nearest) * nearest)


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")

    if isinstance(value, pd.Series):
        return value.to_dict()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]

    if isinstance(value, Path):
        return str(value)

    if _is_missing(value):
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value