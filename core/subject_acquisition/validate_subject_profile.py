from __future__ import annotations

from core.address_subject_profile import (
    blank_subject_profile,
    is_missing,
    missing_required_fields,
    subject_profile_ready,
)


VALID_PROPERTY_TYPES = {
    "detached",
    "single family residence",
    "single family",
    "residential",
    "townhouse",
    "attached",
    "condo",
    "condominium",
    "duplex",
    "half duplex",
    "patio home",
    "row house",
}

PROPERTY_TYPE_ALIASES = {
    "sfr": "Single Family Residence",
    "single family": "Single Family Residence",
    "single-family": "Single Family Residence",
    "single family residence": "Single Family Residence",
    "residential": "Residential",
    "condo": "Condominium",
    "condominium": "Condominium",
    "townhome": "Townhouse",
    "townhouse": "Townhouse",
    "attached": "Attached",
    "detached": "Detached",
    "duplex": "Duplex",
    "half duplex": "Half Duplex",
}

LEVEL_ALIASES = {
    "1": "One",
    "one": "One",
    "one story": "One",
    "1 story": "One",
    "one-story": "One",
    "1-story": "One",
    "ranch": "One",
    "ranch style": "One",
    "2": "Two",
    "two": "Two",
    "two story": "Two",
    "2 story": "Two",
    "two-story": "Two",
    "2-story": "Two",
    "tri": "Tri-Level",
    "tri level": "Tri-Level",
    "tri-level": "Tri-Level",
    "bi": "Bi-Level",
    "bi level": "Bi-Level",
    "bi-level": "Bi-Level",
    "split": "Multi/Split",
    "split level": "Multi/Split",
    "split-level": "Multi/Split",
    "multi split": "Multi/Split",
    "multi/split": "Multi/Split",
    "multi-level": "Multi/Split",
    "multilevel": "Multi/Split",
    "three or more": "Three Or More",
    "3 or more": "Three Or More",
    "three+": "Three Or More",
}


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_number(value: object) -> int | float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value if value > 0 else None

    text = str(value).strip().replace(",", "")
    if not text:
        return None

    try:
        number = float(text)
    except ValueError:
        return None

    if number <= 0:
        return None

    return int(number) if number.is_integer() else number


def normalize_property_type(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    lowered = text.lower()
    return PROPERTY_TYPE_ALIASES.get(lowered, text.title())


def normalize_levels(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    lowered = text.lower()
    return LEVEL_ALIASES.get(lowered, text)


def _derive_unfinished_basement(candidate: dict) -> None:
    basement = candidate.get("basement_sqft")
    finished = candidate.get("finished_basement_sqft")
    unfinished = candidate.get("unfinished_basement_sqft")

    if unfinished is None and basement is not None and finished is not None:
        inferred = basement - finished
        if inferred >= 0:
            candidate["unfinished_basement_sqft"] = inferred


def validate_subject_profile(profile: dict | None) -> dict:
    candidate = blank_subject_profile()

    if profile:
        candidate.update(profile)

    candidate["subject_address"] = _clean_text(candidate.get("subject_address"))
    candidate["above_grade_sqft"] = _clean_number(candidate.get("above_grade_sqft"))
    candidate["property_type"] = normalize_property_type(candidate.get("property_type"))
    candidate["property_subtype"] = _clean_text(candidate.get("property_subtype"))
    candidate["levels"] = normalize_levels(candidate.get("levels"))
    candidate["subject_layout_notes"] = _clean_text(candidate.get("subject_layout_notes"))

    candidate["beds"] = _clean_number(candidate.get("beds"))
    candidate["baths"] = _clean_number(candidate.get("baths"))
    candidate["year_built"] = _clean_number(candidate.get("year_built"))
    candidate["real_avm"] = _clean_number(candidate.get("real_avm"))
    candidate["real_avm_range_low"] = _clean_number(candidate.get("real_avm_range_low"))
    candidate["real_avm_range_high"] = _clean_number(candidate.get("real_avm_range_high"))
    candidate["zillow_estimate"] = _clean_number(candidate.get("zillow_estimate"))
    candidate["redfin_estimate"] = _clean_number(candidate.get("redfin_estimate"))

    candidate["lot_size_sqft"] = _clean_number(candidate.get("lot_size_sqft"))
    candidate["lot_sqft"] = _clean_number(candidate.get("lot_sqft"))
    candidate["style"] = _clean_text(candidate.get("style"))
    candidate["stories"] = _clean_text(candidate.get("stories"))

    candidate["basement_sqft"] = _clean_number(candidate.get("basement_sqft"))
    candidate["finished_basement_sqft"] = _clean_number(candidate.get("finished_basement_sqft"))
    candidate["unfinished_basement_sqft"] = _clean_number(candidate.get("unfinished_basement_sqft"))
    candidate["total_finished_sqft"] = _clean_number(candidate.get("total_finished_sqft"))
    candidate["building_area_total"] = _clean_number(candidate.get("building_area_total"))
    candidate["summary_building_sqft"] = _clean_number(candidate.get("summary_building_sqft"))
    candidate["above_grade_source"] = _clean_text(candidate.get("above_grade_source"))

    candidate["county"] = _clean_text(candidate.get("county"))
    candidate["apn"] = _clean_text(candidate.get("apn"))
    candidate["clip"] = _clean_text(candidate.get("clip"))
    candidate["schedule_number"] = _clean_text(candidate.get("schedule_number"))
    candidate["neighborhood_name"] = _clean_text(candidate.get("neighborhood_name"))
    candidate["neighborhood_code"] = _clean_text(candidate.get("neighborhood_code"))
    candidate["subdivision"] = _clean_text(candidate.get("subdivision"))
    candidate["zoning"] = _clean_text(candidate.get("zoning"))

    candidate["school_district"] = _clean_text(candidate.get("school_district"))
    candidate["elementary_school"] = _clean_text(candidate.get("elementary_school"))
    candidate["middle_school"] = _clean_text(candidate.get("middle_school"))
    candidate["high_school"] = _clean_text(candidate.get("high_school"))

    _derive_unfinished_basement(candidate)

    candidate["subject_profile_ready"] = subject_profile_ready(candidate)
    candidate["missing_required_fields"] = missing_required_fields(candidate)

    return candidate


def required_subject_fields_present(profile: dict) -> bool:
    return subject_profile_ready(validate_subject_profile(profile))
