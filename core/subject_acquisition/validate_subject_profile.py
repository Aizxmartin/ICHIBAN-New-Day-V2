from __future__ import annotations

from core.address_subject_profile import blank_subject_profile, is_missing, missing_required_fields, subject_profile_ready


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



def validate_subject_profile(profile: dict | None) -> dict:
    candidate = blank_subject_profile()
    if profile:
        candidate.update(profile)

    candidate["subject_address"] = _clean_text(candidate.get("subject_address"))
    candidate["above_grade_sqft"] = _clean_number(candidate.get("above_grade_sqft"))
    candidate["property_type"] = normalize_property_type(candidate.get("property_type"))
    candidate["property_subtype"] = _clean_text(candidate.get("property_subtype"))
    candidate["beds"] = _clean_number(candidate.get("beds"))
    candidate["baths"] = _clean_number(candidate.get("baths"))
    candidate["year_built"] = _clean_number(candidate.get("year_built"))
    candidate["real_avm"] = _clean_number(candidate.get("real_avm"))
    candidate["real_avm_range_low"] = _clean_number(candidate.get("real_avm_range_low"))
    candidate["real_avm_range_high"] = _clean_number(candidate.get("real_avm_range_high"))
    candidate["lot_size_sqft"] = _clean_number(candidate.get("lot_size_sqft"))
    candidate["style"] = _clean_text(candidate.get("style"))
    candidate["stories"] = _clean_text(candidate.get("stories"))
    candidate["basement_sqft"] = _clean_number(candidate.get("basement_sqft"))
    candidate["finished_basement_sqft"] = _clean_number(candidate.get("finished_basement_sqft"))

    candidate["subject_profile_ready"] = subject_profile_ready(candidate)
    candidate["missing_required_fields"] = missing_required_fields(candidate)
    return candidate



def required_subject_fields_present(profile: dict) -> bool:
    return subject_profile_ready(validate_subject_profile(profile))
