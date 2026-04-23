from __future__ import annotations

import re
from typing import Any


SUBJECT_TO_STANDARD = {
    "Bldg Sq Ft - Finished": "above_grade_sqft",
    "Bldg Sq Ft - Above Ground": "above_grade_sqft",
    "Above Ground Sq Ft": "above_grade_sqft",
    "Above Grade Finished Area": "above_grade_sqft",
    "Above Grade Finished Sq Ft": "above_grade_sqft",
    "Above Grade Sq Ft": "above_grade_sqft",
    "Above Grade Area": "above_grade_sqft",
    "Gross Living Area": "above_grade_sqft",
    "Living Area": "above_grade_sqft",
    "Main Level Sq Ft": "above_grade_sqft",
    "Main Level Area": "above_grade_sqft",
    "Main Level Living Area": "above_grade_sqft",
    "Finished Area Above Grade": "above_grade_sqft",
    "Bldg Sq Ft - Basement": "basement_sqft",
    "Basement Sq Ft": "basement_sqft",
    "Basement SF": "basement_sqft",
    "Basement Area": "basement_sqft",
    "Bldg Sq Ft - Finished Basement": "finished_basement_sqft",
    "Finished Basement Sq Ft": "finished_basement_sqft",
    "Finished Basement SF": "finished_basement_sqft",
    "Bsmt Finished Area": "finished_basement_sqft",
    "Finished Basement": "finished_basement_sqft",
    "Land Use - County": "property_type",
    "Land Use": "property_type",
    "Property Type": "property_type",
    "Type": "property_type",
    "Residential Type": "property_type",
    "Land Use - CoreLogic": "property_subtype",
    "Property Sub Type": "property_subtype",
    "Property Subtype": "property_subtype",
    "Sub Type": "property_subtype",
    "Style": "property_subtype",
    "SFR": "property_subtype",
    "Year Built": "year_built",
    "Actual Year Built": "year_built",
    "RealAVM": "real_avm",
    "Real AVM": "real_avm",
    "RealAVM Range Low": "real_avm_range_low",
    "RealAVM Range High": "real_avm_range_high",
    "Real AVM Range Low": "real_avm_range_low",
    "Real AVM Range High": "real_avm_range_high",
    "Beds": "beds",
    "Bedrooms": "beds",
    "Total Bedrooms": "beds",
    "Baths": "baths",
    "Bathrooms": "baths",
    "Total Baths": "baths",
    "Bathrooms Total": "baths",
    "Garage Spaces": "garage_spaces",
    "Lot Size": "lot_size_sqft",
    "Lot Size Sq Ft": "lot_size_sqft",
    "Lot Sq Ft": "lot_size_sqft",
    "Site Area": "lot_size_sqft",
    "Property Address": "subject_address",
    "Subject Address": "subject_address",
    "Address": "subject_address",
    "Situs Address": "subject_address",
    "Property Location": "subject_address",
}

FIELD_LABEL_ALIASES: dict[str, list[str]] = {}
for raw_label, standard_key in SUBJECT_TO_STANDARD.items():
    FIELD_LABEL_ALIASES.setdefault(standard_key, []).append(raw_label)

FIELD_LABEL_ALIASES.setdefault('real_avm_range', []).extend([
    'RealAVM Range',
    'Real AVM Range',
])

PROPERTY_TYPE_CANDIDATES = [
    'Land Use - County',
    'Land Use',
    'Property Type',
    'Type',
    'Residential Type',
]

PROPERTY_SUBTYPE_CANDIDATES = [
    'Land Use - CoreLogic',
    'Property Sub Type',
    'Property Subtype',
    'Sub Type',
    'Style',
    'SFR',
]

PROPERTY_TYPE_ALIASES = {
    'sfr': 'Single Family Residence',
    'single family': 'Single Family Residence',
    'single-family': 'Single Family Residence',
    'single family residence': 'Single Family Residence',
    'residential': 'Residential',
    'condo': 'Condominium',
    'condominium': 'Condominium',
    'townhome': 'Townhouse',
    'townhouse': 'Townhouse',
    'attached': 'Attached',
    'detached': 'Detached',
    'duplex': 'Duplex',
    'half duplex': 'Half Duplex',
    'patio home': 'Patio Home',
    'row house': 'Row House',
}

PROPERTY_SUBTYPE_ALIASES = {
    'sfr': 'SFR',
    'single family': 'SFR',
    'single family residence': 'SFR',
    'detached': 'SFR',
    'ranch': 'Ranch',
    'two story': 'Two Story',
    'tri-level': 'Tri-Level',
    'tri level': 'Tri-Level',
    'bi-level': 'Bi-Level',
    'bi level': 'Bi-Level',
    'townhouse': 'Townhome',
    'townhome': 'Townhome',
    'condominium': 'Condo',
    'condo': 'Condo',
}

NUMBER_RE = re.compile(r'\$?\s*([\d,]+(?:\.\d+)?)')


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {'n/a', 'na', 'none', 'null', '--'}:
            return None
    return value


def to_float(value: Any) -> float | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace('$', '').replace(',', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    num = to_float(value)
    if num is None:
        return None
    return int(round(num))


def extract_number(value: Any) -> int | float | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    match = NUMBER_RE.search(str(value))
    if not match:
        return None
    cleaned = match.group(1).replace(',', '')
    number = float(cleaned)
    return int(number) if number.is_integer() else number


def normalize_property_type(value: Any) -> str | None:
    text = clean_value(value)
    if text is None:
        return None
    lowered = str(text).strip().lower()
    return PROPERTY_TYPE_ALIASES.get(lowered, str(text).strip().title())


def normalize_property_subtype(value: Any, fallback_type: str | None = None) -> str | None:
    text = clean_value(value)
    if text is not None:
        lowered = str(text).strip().lower()
        return PROPERTY_SUBTYPE_ALIASES.get(lowered, str(text).strip().title())
    if fallback_type == 'Single Family Residence':
        return 'SFR'
    return None
