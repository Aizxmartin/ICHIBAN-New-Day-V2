from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import pandas as pd

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "field_reference_map.json"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    FIELD_REFERENCE_MAP: Dict[str, Dict[str, Any]] = json.load(f)


@dataclass
class MarketInspection:
    dataframe: pd.DataFrame
    matched_fields: Dict[str, str]
    missing_preferred_fields: list[str]
    detected_header_row: int
    header_score: int


def get_source_field_map() -> Dict[str, str]:
    return {
        internal_name: spec["source_field"]
        for internal_name, spec in FIELD_REFERENCE_MAP.items()
        if spec.get("source_field")
    }


def get_required_core_fields() -> Tuple[str, ...]:
    return (
        "mls_status",
        "net_close_price",
        "close_price",
        "above_grade_sqft",
        "beds",
        "baths",
        "year_built",
        "days_in_mls",
        "property_type",
        "property_subtype",
    )


def normalize_market_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    source_map = get_source_field_map()
    for internal_name, source_field in source_map.items():
        normalized[internal_name] = row.get(source_field)
    return normalized


def normalize_market_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, str]]:
    rename_map: Dict[str, str] = {}
    source_map = get_source_field_map()

    for internal_name, source_field in source_map.items():
        if source_field in df.columns:
            rename_map[source_field] = internal_name

    normalized_df = df.rename(columns=rename_map).copy()
    return normalized_df, rename_map


def get_missing_required_fields(
    df_columns: Iterable[str],
    required_internal_fields: Iterable[str],
) -> Dict[str, str]:
    df_columns = set(df_columns)
    missing: Dict[str, str] = {}
    source_map = get_source_field_map()

    for internal_name in required_internal_fields:
        source_field = source_map.get(internal_name)
        if source_field and source_field not in df_columns:
            missing[internal_name] = source_field

    return missing


def inspect_market_file(df: pd.DataFrame) -> MarketInspection:
    normalized_df, rename_map = normalize_market_dataframe(df)

    matched_fields = {
        internal_name: source_field
        for source_field, internal_name in rename_map.items()
    }

    missing_required = get_missing_required_fields(
        df.columns,
        get_required_core_fields(),
    )

    return MarketInspection(
        dataframe=normalized_df,
        matched_fields=matched_fields,
        missing_preferred_fields=list(missing_required.keys()),
        detected_header_row=1,
        header_score=len(matched_fields),
    )