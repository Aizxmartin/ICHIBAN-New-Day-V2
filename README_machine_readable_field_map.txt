# Machine-readable field map build

This package adds a computer-readable field map for ICHIBAN.

Files included:
- `core/config/field_reference_map.json`
- `core/market_mapping.py`

Purpose:
- keep the human `.docx` reference as the readable source of truth
- give the app a stable machine-readable map using the official MLS field names
- map raw MLS columns into ICHIBAN internal field names

Status rule locked to project standard:
- `mls_status` uses only `Mls Status`
- `Standard Status` is not used


SCHEMA REPAIR 2026-07-11
- `Bldg Sq Ft - Finished` maps to `total_finished_sqft`, never `above_grade_sqft`.
- `Bldg Sq Ft - Above Ground` maps to `above_grade_sqft`.
- `Total Finished Area` is not an alias for `building_area_total`.
- Generic `ppsf` / `psf` fields are prohibited. Use `net_close_psf_above_grade` when the numerator is Net Close Price and the denominator is Above Grade Finished Area.
- `Standard Status` is not accepted as an MLS status fallback.
