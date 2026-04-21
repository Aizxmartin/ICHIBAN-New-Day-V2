from __future__ import annotations

from copy import deepcopy

from core.subject_acquisition.validate_subject_profile import validate_subject_profile


PREFERRED_FIELD_ORDER = [
    "subject_address",
    "above_grade_sqft",
    "property_type",
    "property_subtype",
    "beds",
    "baths",
    "year_built",
    "real_avm",
    "real_avm_range_low",
    "real_avm_range_high",
    "lot_size_sqft",
    "style",
    "stories",
    "basement_sqft",
    "finished_basement_sqft",
]



def merge_subject_sources(base_profile: dict | None, incoming_profile: dict | None, source_name: str) -> dict:
    merged = deepcopy(base_profile or {})
    merged.setdefault("field_sources", {})
    merged.setdefault("source_summary", [])

    if not incoming_profile:
        return validate_subject_profile(merged)

    for field in PREFERRED_FIELD_ORDER:
        value = incoming_profile.get(field)
        if value is None or value == "":
            continue
        current = merged.get(field)
        if current is None or current == "":
            merged[field] = value
            merged["field_sources"][field] = source_name

    if source_name and source_name not in merged["source_summary"]:
        merged["source_summary"].append(source_name)

    return validate_subject_profile(merged)
