# TARZAN v20.5.3 — Single Report Notes Field Patch Audit

## Purpose
Reduce Module 5 Report Context to one first-run notes field so the Tarzan valuation branch is not confused by separate seller goal, buyer consideration, showing feedback, listing history, upgrade, and after-active fields.

## Why
The first-run ICHIBAN INSIGHT / Tarzan valuation branch is primarily pre-appointment. It should accept concise field intelligence learned from a seller conversation, visit, photos, or known condition/marketability concern, but it should not become a full after-active tactical review.

## Changed files
- `app/pages/5_Insight_Report.py`
- `core/report_input_builder.py`

## App changes
- Replaced multiple Report Context note boxes with one field: `Report Notes / Field Intelligence for Tarzan`.
- Preserved Report Date and manual range override controls.
- Clear Context now clears the new single notes key and old legacy note keys.
- Build / Refresh Tarzan Report Input passes the single notes field as the only Realtor field-intelligence input.
- Removed first-run UI fields for seller goal, buyer consideration notes, upgrade notes, showing feedback notes, listing history notes, and confirmed current list price. Those belong in a future Retrospect / after-active workflow if needed.

## Report input changes
- `additional_notes_provided.categories` now contains one category only: `Report Notes / Field Intelligence`.
- `report_notes` is stored as the controlling field-intelligence note.
- `realtor_notes` is retained as a compatibility alias using the same text.
- `buyer_consideration_notes` and `listing_history_notes` are intentionally blank in first-run Tarzan.
- Pre-GPT notes review now distinguishes the single notes field from after-active/listing-history fields.

## Governance
- First-run Tarzan notes qualify or verify evidence. They do not silently rewrite comp-adjustment math.
- Detailed showing logs, relist history, cumulative exposure, and tactical pricing review belong in ICHIBAN Retrospect later.
- BBC remains paused. Retrospect remains paused.

## Tests run
- `python -m compileall -q app core`
- Built a report input from `valuation_engine_output (6).json` with sample notes.
- Confirmed output contains `report_notes` and one `Report Notes / Field Intelligence` category.
- Confirmed seller goal, buyer consideration, showing feedback, and listing-history categories do not appear in the generated prompt.

## Status
PASS for local testing. Server push still HOLD until local output is verified.
