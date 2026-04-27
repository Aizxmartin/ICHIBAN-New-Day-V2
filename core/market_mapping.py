from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pandas as pd

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "field_reference_map.json"


def _load_field_reference_map() -> Dict[str, Dict[str, Any]]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    return {}


FIELD_REFERENCE_MAP: Dict[str, Dict[str, Any]] = _load_field_reference_map()

# Fallback aliases protect the app when the MLS export capitalization or label
# differs from the machine-readable field map.
MARKET_FIELD_ALIASES: Dict[str, List[str]] = {
    "listing_id": ["Listing ID", "MLS Number", "MLS #", "MLS Num"],
    "mls_status": ["Mls Status", "MLS Status", "Status", "Standard Status"],
    "street_number": ["Street Number Numeric", "Street Number"],
    "street_name": ["Street Name"],
    "street_suffix": ["Street Suffix"],
    "street_dir_prefix": ["Street Dir Prefix", "Street Direction Prefix"],
    "street_dir_suffix": ["Street Dir Suffix", "Street Direction Suffix"],
    "full_address": ["Full Address", "Property Address", "Street Address", "Address"],
    "property_type": ["Property Type", "Property Type Category"],
    "property_subtype": ["Property Sub Type", "Property Subtype", "Structure Type"],
    "above_grade_sqft": ["Above Grade Finished Area", "Above Grade SqFt", "AG SF", "Main SqFt"],
    "basement_sqft": ["Basement SF", "Bldg Sq Ft - Basement", "Total Basement Area", "Basement Area"],
    "finished_basement_sqft": ["Below Grade Finished Area", "Basement Finished Area", "Finished Basement SqFt", "Bldg Sq Ft - Finished Basement"],
    "below_grade_finished_sqft": ["Below Grade Finished Area", "Basement Finished Area", "Finished Basement SqFt"],
    "below_grade_unfinished_sqft": ["Below Grade Unfinished Area", "Basement Unfinished Area", "Unfinished Basement SqFt"],
    "building_area_total": ["Building Area Total", "Total SqFt", "Total Finished Area"],
    "beds": ["Bedrooms Total", "Beds Total", "Bedrooms", "Beds"],
    "baths": ["Bathrooms Total Integer", "Bathrooms Total Decimal", "Baths Total", "Bathrooms", "Baths"],
    "year_built": ["Year Built"],
    "list_price": ["List Price", "Current Price"],
    "original_list_price": ["Original List Price"],
    "close_price": ["Close Price", "Sold Price", "Sold Price/Close Price", "Closed Price"],
    "net_close_price": ["Net Close Price"],
    "concessions": ["Concessions Amount", "Seller Concessions", "Concessions"],
    "concessions_amount": ["Concessions Amount", "Seller Concessions", "Concessions"],
    "days_in_mls": ["Days In MLS", "Days in MLS", "DOM", "Cumulative Days on Market", "Days on Market"],
    "close_date": ["Close Date", "Sold Date"],
    "list_date": ["List Date", "On Market Date", "Listing Contract Date"],
    "listing_contract_date": ["Listing Contract Date", "List Date", "On Market Date"],
    "purchase_contract_date": ["Purchase Contract Date", "Under Contract Date"],
    "public_remarks": ["Public Remarks", "Remarks"],
    "private_remarks": ["Private Remarks", "Broker Remarks", "Confidential Remarks"],
    "broker_remarks": ["Broker Remarks", "Private Remarks", "Confidential Remarks"],
    "subdivision_name": ["Subdivision Name", "Subdivision", "Neighborhood"],
    "subdivision": ["Subdivision Name", "Subdivision", "Neighborhood"],
    "levels": ["Levels"],
    "garage_spaces": ["Garage Spaces"],
    "lot_size_sqft": ["Lot Size Square Feet", "Lot Size Sq Ft", "Lot Sq Ft"],
    "lot_size_acres": ["Lot Size Acres"],
    "lot_features": ["Lot Features"],
    "architectural_style": ["Architectural Style"],
    "property_condition": ["Property Condition"],
    "postal_code": ["Postal Code", "Zip", "ZIP Code"],
}

NUMERIC_FIELDS = {
    "above_grade_sqft",
    "basement_sqft",
    "finished_basement_sqft",
    "below_grade_finished_sqft",
    "below_grade_unfinished_sqft",
    "building_area_total",
    "beds",
    "baths",
    "year_built",
    "list_price",
    "original_list_price",
    "close_price",
    "net_close_price",
    "concessions",
    "concessions_amount",
    "days_in_mls",
    "garage_spaces",
    "lot_size_sqft",
    "lot_size_acres",
}


@dataclass
class MarketInspection:
    dataframe: pd.DataFrame
    matched_fields: Dict[str, str]
    missing_preferred_fields: List[str]
    detected_header_row: int
    header_score: int


def _clean_column_name(name: Any) -> str:
    return str(name).strip()


def _norm_label(value: Any) -> str:
    return str(value).strip().lower().replace("_", " ").replace("  ", " ")


def get_source_field_map() -> Dict[str, str]:
    return {
        internal_name: spec.get("source_field")
        for internal_name, spec in FIELD_REFERENCE_MAP.items()
        if isinstance(spec, dict) and spec.get("source_field")
    }


def get_aliases_for_field(internal_name: str) -> List[str]:
    aliases: List[str] = []
    source_field = get_source_field_map().get(internal_name)
    if source_field:
        aliases.append(source_field)
    aliases.extend(MARKET_FIELD_ALIASES.get(internal_name, []))

    # De-dupe while preserving order.
    seen = set()
    cleaned: List[str] = []
    for alias in aliases:
        key = _norm_label(alias)
        if key not in seen:
            cleaned.append(alias)
            seen.add(key)
    return cleaned


def get_required_core_fields() -> Tuple[str, ...]:
    return (
        "mls_status",
        "close_price",
        "above_grade_sqft",
        "beds",
        "baths",
        "year_built",
        "days_in_mls",
        "property_type",
        "property_subtype",
    )


def _lookup_column(columns: Iterable[Any], aliases: Iterable[str]) -> Optional[str]:
    normalized = {_norm_label(c): str(c).strip() for c in columns}
    for alias in aliases:
        match = normalized.get(_norm_label(alias))
        if match is not None:
            return match
    return None


def _header_clues() -> set[str]:
    clues = set()
    for internal_name in set(MARKET_FIELD_ALIASES) | set(FIELD_REFERENCE_MAP):
        for alias in get_aliases_for_field(internal_name):
            clues.add(_norm_label(alias))
    return clues


def score_headers(columns: Iterable[Any]) -> int:
    clues = _header_clues()
    return sum(1 for c in columns if _norm_label(c) in clues)


def _read_csv_with_fallback(uploaded_file) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Could not read CSV file: {last_error}")


def load_market_file_with_header_detection(market_file) -> tuple[pd.DataFrame, int, int]:
    name = getattr(market_file, "name", "").lower()

    if name.endswith(".csv"):
        df = _read_csv_with_fallback(market_file)
        df.columns = [_clean_column_name(c) for c in df.columns]
        return df, 0, score_headers(df.columns)

    best_df: Optional[pd.DataFrame] = None
    best_score = -1
    best_header_row = 0

    # MLS Excel exports often include report title/meta rows before the true header.
    for header_row in range(0, 31):
        try:
            if hasattr(market_file, "seek"):
                market_file.seek(0)
            df = pd.read_excel(market_file, header=header_row)
            df.columns = [_clean_column_name(c) for c in df.columns]
            df = df.dropna(axis=1, how="all")
            score = score_headers(df.columns)
            if score > best_score:
                best_df = df
                best_score = score
                best_header_row = header_row
        except Exception:
            continue

    if best_df is None:
        raise ValueError("Could not read market file. Confirm it is a valid CSV/XLSX MLS export.")

    return best_df, best_header_row, best_score


def _to_number(value: pd.Series) -> pd.Series:
    return pd.to_numeric(
        value.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def normalize_market_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for internal_name in set(MARKET_FIELD_ALIASES) | set(FIELD_REFERENCE_MAP):
        for alias in get_aliases_for_field(internal_name):
            if alias in row:
                normalized[internal_name] = row.get(alias)
                break
    return normalized


def normalize_market_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, str], List[str]]:
    working = df.copy()
    working.columns = [_clean_column_name(c) for c in working.columns]
    working = working.dropna(axis=1, how="all")

    normalized = working.copy()
    matched_fields: Dict[str, str] = {}

    for internal_name in set(MARKET_FIELD_ALIASES) | set(FIELD_REFERENCE_MAP):
        source_col = _lookup_column(working.columns, get_aliases_for_field(internal_name))
        if source_col is not None:
            normalized[internal_name] = working[source_col]
            matched_fields[internal_name] = source_col

    if "above_grade_sqft" not in normalized.columns and "building_area_total" in normalized.columns and "basement_sqft" in normalized.columns:
        normalized["above_grade_sqft"] = _to_number(normalized["building_area_total"]) - _to_number(normalized["basement_sqft"])

    if "finished_basement_sqft" not in normalized.columns and "below_grade_finished_sqft" in normalized.columns:
        normalized["finished_basement_sqft"] = normalized["below_grade_finished_sqft"]

    if "basement_sqft" not in normalized.columns:
        finished = _to_number(normalized["below_grade_finished_sqft"]) if "below_grade_finished_sqft" in normalized.columns else None
        unfinished = _to_number(normalized["below_grade_unfinished_sqft"]) if "below_grade_unfinished_sqft" in normalized.columns else None
        if finished is not None and unfinished is not None:
            normalized["basement_sqft"] = finished.fillna(0) + unfinished.fillna(0)

    for field in NUMERIC_FIELDS.intersection(normalized.columns):
        normalized[field] = _to_number(normalized[field])

    if "net_close_price" not in normalized.columns and "close_price" in normalized.columns:
        concessions_col = None
        for candidate in ("concessions", "concessions_amount"):
            if candidate in normalized.columns:
                concessions_col = candidate
                break
        concessions = _to_number(normalized[concessions_col]).fillna(0) if concessions_col else 0
        normalized["net_close_price"] = _to_number(normalized["close_price"]) - concessions

    if "above_grade_sqft" in normalized.columns and "net_close_price" in normalized.columns:
        ag = pd.to_numeric(normalized["above_grade_sqft"], errors="coerce")
        price = pd.to_numeric(normalized["net_close_price"], errors="coerce")
        normalized["ppsf"] = price.where(ag > 0) / ag.where(ag > 0)

    missing = [field for field in get_required_core_fields() if field not in normalized.columns]

    return normalized, matched_fields, missing


def inspect_market_file(market_input: Union[pd.DataFrame, Any]) -> MarketInspection:
    """
    Inspect either an uploaded file object or an already-loaded dataframe.

    Module 3 can pass the upload directly. Tests or later controllers may pass a
    dataframe that has already gone through custom header detection.
    """
    if isinstance(market_input, pd.DataFrame):
        raw_df = market_input.copy()
        raw_df.columns = [_clean_column_name(c) for c in raw_df.columns]
        header_row = 0
        header_score = score_headers(raw_df.columns)
    else:
        raw_df, header_row, header_score = load_market_file_with_header_detection(market_input)

    normalized, matched_fields, missing = normalize_market_dataframe(raw_df)
    return MarketInspection(
        dataframe=normalized,
        matched_fields=matched_fields,
        missing_preferred_fields=missing,
        detected_header_row=header_row,
        header_score=header_score,
    )
