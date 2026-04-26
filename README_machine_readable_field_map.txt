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
