from copy import deepcopy
from core.subject_requirements import REQUIRED_SUBJECT_FIELDS


def blank_subject_profile(address: str = "") -> dict:
    return {
        "subject_address": address.strip() or None,
        "above_grade_sqft": None,
        "property_type": None,
        "property_subtype": None,
        "beds": None,
        "baths": None,
        "year_built": None,
        "real_avm": None,
        "real_avm_range_low": None,
        "real_avm_range_high": None,
        "lot_size_sqft": None,
        "style": None,
        "stories": None,
        "basement_sqft": None,
        "finished_basement_sqft": None,
        "source_summary": [],
        "field_sources": {},
        "subject_profile_ready": False,
        "subject_acquisition_status": "not_started",
    }


def is_missing(value) -> bool:
    return value is None or value == ""


def update_field(profile: dict, field: str, value, source: str) -> dict:
    updated = deepcopy(profile)
    updated[field] = value
    updated.setdefault("field_sources", {})[field] = source
    updated.setdefault("source_summary", [])
    if source and source not in updated["source_summary"]:
        updated["source_summary"].append(source)
    updated["subject_profile_ready"] = subject_profile_ready(updated)
    return updated


def subject_profile_ready(profile: dict) -> bool:
    return all(not is_missing(profile.get(field)) for field in REQUIRED_SUBJECT_FIELDS)


def missing_required_fields(profile: dict) -> list[str]:
    return [field for field in REQUIRED_SUBJECT_FIELDS if is_missing(profile.get(field))]
