from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


MARKET_FIELD_ALIASES = {
    "listing_id": ["Listing ID", "MLS Number", "MLS #", "MLS Num"],
    "mls_status": ["MLS Status", "Status", "Standard Status"],
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
    "finished_basement_sqft": ["Basement Finished Area", "Finished Basement SqFt", "Bldg Sq Ft - Finished Basement"],
    "building_area_total": ["Building Area Total", "Total SqFt", "Total Finished Area"],
    "beds": ["Bedrooms Total", "Beds Total", "Bedrooms", "Beds"],
    "baths": ["Bathrooms Total Integer", "Bathrooms Total Decimal", "Baths Total", "Bathrooms", "Baths"],
    "year_built": ["Year Built"],
    "list_price": ["List Price", "Current Price"],
    "close_price": ["Close Price", "Sold Price", "Sold Price/Close Price", "Closed Price"],
    "concessions": ["Concessions Amount", "Seller Concessions", "Concessions"],
    "days_in_mls": ["Days in MLS", "DOM", "Cumulative Days on Market", "Days on Market"],
    "close_date": ["Close Date", "Sold Date"],
    "list_date": ["List Date", "On Market Date"],
    "public_remarks": ["Public Remarks", "Remarks"],
    "broker_remarks": ["Broker Remarks", "Private Remarks", "Confidential Remarks"],
    "subdivision": ["Subdivision Name", "Subdivision", "Neighborhood"],
}

EXPECTED_HEADER_CLUES = {
    "listing id",
    "mls status",
    "property type",
    "property sub type",
    "above grade finished area",
    "close price",
    "list price",
    "days in mls",
}

NUMERIC_FIELDS = {
    "above_grade_sqft",
    "basement_sqft",
    "finished_basement_sqft",
    "building_area_total",
    "beds",
    "baths",
    "year_built",
    "list_price",
    "close_price",
    "concessions",
    "days_in_mls",
}


@dataclass
class MarketInspection:
    dataframe: pd.DataFrame
    detected_header_row: int
    header_score: int
    matched_fields: dict[str, str]
    missing_preferred_fields: list[str]


def _clean_column_name(name: Any) -> str:
    return str(name).strip()


def _lookup_column(columns: list[str], aliases: list[str]) -> str | None:
    normalized = {str(c).strip().lower(): c for c in columns}
    for alias in aliases:
        match = normalized.get(alias.strip().lower())
        if match is not None:
            return match
    return None


def score_headers(columns: list[Any]) -> int:
    score = 0
    cleaned = [str(c).strip().lower() for c in columns]
    for col in cleaned:
        if col in EXPECTED_HEADER_CLUES:
            score += 1
    return score


def load_market_file_with_header_detection(market_file) -> tuple[pd.DataFrame, int, int]:
    name = getattr(market_file, "name", "").lower()
    if name.endswith(".csv"):
        if hasattr(market_file, "seek"):
            market_file.seek(0)
        df = pd.read_csv(market_file)
        return df, 0, score_headers(df.columns)

    best_df = None
    best_score = -1
    best_header_row = 0

    for header_row in range(0, 10):
        if hasattr(market_file, "seek"):
            market_file.seek(0)
        df = pd.read_excel(market_file, header=header_row)
        score = score_headers(df.columns)
        if score > best_score:
            best_df = df
            best_score = score
            best_header_row = header_row

    if best_df is None:
        raise ValueError("Could not read market file.")

    return best_df, best_header_row, best_score


def normalize_market_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    working = df.copy()
    working.columns = [_clean_column_name(c) for c in working.columns]
    matched_fields: dict[str, str] = {}

    normalized = pd.DataFrame(index=working.index)

    for standard_field, aliases in MARKET_FIELD_ALIASES.items():
        source_col = _lookup_column(list(working.columns), aliases)
        if source_col is not None:
            normalized[standard_field] = working[source_col]
            matched_fields[standard_field] = source_col

    if "above_grade_sqft" not in normalized.columns and "building_area_total" in normalized.columns and "basement_sqft" in normalized.columns:
        normalized["above_grade_sqft"] = pd.to_numeric(normalized["building_area_total"], errors="coerce") - pd.to_numeric(normalized["basement_sqft"], errors="coerce")

    if "finished_basement_sqft" not in normalized.columns and "basement_sqft" in normalized.columns:
        normalized["finished_basement_sqft"] = pd.NA

    for field in NUMERIC_FIELDS.intersection(normalized.columns):
        normalized[field] = pd.to_numeric(normalized[field], errors="coerce")

    if "close_price" in normalized.columns:
        concessions = pd.to_numeric(normalized.get("concessions", 0), errors="coerce").fillna(0)
        normalized["net_close_price"] = pd.to_numeric(normalized["close_price"], errors="coerce") - concessions

    if "above_grade_sqft" in normalized.columns and "net_close_price" in normalized.columns:
        ag = pd.to_numeric(normalized["above_grade_sqft"], errors="coerce")
        price = pd.to_numeric(normalized["net_close_price"], errors="coerce")
        normalized["ppsf"] = price.where(ag > 0) / ag.where(ag > 0)

    preferred = [
        "mls_status",
        "property_type",
        "property_subtype",
        "above_grade_sqft",
        "beds",
        "baths",
        "year_built",
        "list_price",
        "close_price",
        "days_in_mls",
    ]
    missing = [field for field in preferred if field not in normalized.columns]

    return normalized, matched_fields, missing


def inspect_market_file(market_file) -> MarketInspection:
    df, header_row, header_score = load_market_file_with_header_detection(market_file)
    normalized, matched_fields, missing = normalize_market_dataframe(df)
    return MarketInspection(
        dataframe=normalized,
        detected_header_row=header_row,
        header_score=header_score,
        matched_fields=matched_fields,
        missing_preferred_fields=missing,
    )
