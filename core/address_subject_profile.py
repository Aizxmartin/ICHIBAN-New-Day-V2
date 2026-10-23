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

        # AVM / online estimate support
        "real_avm": None,
        "real_avm_range_low": None,
        "real_avm_range_high": None,
        "zillow_estimate": None,
        "redfin_estimate": None,

        # Size / physical characteristics
        "lot_size_sqft": None,
        "lot_sqft": None,
        "style": None,
        "stories": None,
        "levels": None,
        "subject_layout_notes": None,

        # Basement fields must stay separate from above-grade area
        "basement_sqft": None,
        "finished_basement_sqft": None,
        "unfinished_basement_sqft": None,

        # Location / public-record support
        "county": None,
        "apn": None,
        "clip": None,
        "schedule_number": None,
        "neighborhood_name": None,
        "neighborhood_code": None,
        "subdivision": None,
        "zoning": None,
        "school_district": None,
        "elementary_school": None,
        "middle_school": None,
        "high_school": None,

        # Source / verification tracking
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

    updated.setdefault("field_sources", {})
    updated["field_sources"][field] = source

    updated.setdefault("source_summary", [])
    if source and source not in updated["source_summary"]:
        updated["source_summary"].append(source)

    updated["subject_profile_ready"] = subject_profile_ready(updated)
    updated["missing_required_fields"] = missing_required_fields(updated)

    return updated


def subject_profile_ready(profile: dict) -> bool:
    return all(not is_missing(profile.get(field)) for field in REQUIRED_SUBJECT_FIELDS)


def missing_required_fields(profile: dict) -> list[str]:
    return [
        field
        for field in REQUIRED_SUBJECT_FIELDS
        if is_missing(profile.get(field))
    ]