# ICHIBAN Schema Repair — 2026-07-11

Original upload preserved. This corrected copy removes contradictory square-footage, status, and PSF mappings.

## Corrections

1. `Bldg Sq Ft - Finished` now maps to `total_finished_sqft`, not `above_grade_sqft`.
2. `Bldg Sq Ft - Above Ground` is explicitly mapped to `above_grade_sqft`.
3. `Standard Status` was removed as a fallback for `mls_status`.
4. `Total Finished Area` was removed as an alias for `building_area_total` and maps to `living_area_finished`.
5. Generic `ppsf`, `effective_ppsf`, and `average_ppsf` names were replaced with explicit above-grade names:
   - `net_close_psf_above_grade`
   - `effective_net_close_psf_above_grade`
   - `average_net_close_psf_above_grade`
6. The unsafe subject fallback `finished_sqft -> above_grade_sqft` was removed from the comp engine.
7. The machine-readable field map now includes prohibitions and schema controls.

## 10006 Boca regression facts

- Above Grade Finished Area: 2,065 SF
- Below Grade Total Area: 1,152 SF
- Below Grade Finished Area: 969 SF
- Below Grade Unfinished Area: 183 SF
- Living Area (Finished): 3,034 SF
- Building Area Total: 3,217 SF

These fields must remain separate.


## Runtime repair 2 - 1004MC and Tarzan quality gate
- Removed `confirmed` as a universally required word. A Tarzan report now passes when it states any valid final status: CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED.
- Replaced `st.stop()` inside the report-generation spinner with a normal failed-quality branch so the spinner exits cleanly and the page remains usable.
- Added visual OCR fallback for browser-printed/rasterized 1004MC PDFs. Parsed values are validated against absorption and months-supply math before acceptance.
- Added explicit success handling for OCR-parsed 1004MC reports.
