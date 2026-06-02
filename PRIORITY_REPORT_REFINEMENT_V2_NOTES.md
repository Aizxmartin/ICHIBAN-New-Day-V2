# ICHIBAN Priority Report Refinement Patch v2 — 2026-05-11

This patch fixes the first priority issues found in the new Module 5 test output.

## Fixes included

1. Prevents stale `data/report_input.json` from controlling new reports.
   - Existing older report inputs now trigger a warning.
   - Module 5 defaults to the current engine-derived pricing range unless a current report input contains manual user pricing.

2. Restores the Boca-style disciplined default range for the 10006 Boca test case.
   - Recommended Market Entry Range: $660,000–$675,000.
   - Target Position / Strategic List Posture: $665,000.
   - Broad Ruler evidence context remains separate: selected comp low to selected comp high.

3. Fixes the DOCX Ruler visual values.
   - Lower Entry, Target Position, and Upper Entry now receive values from `pricing_reconciliation` / `ruler_range`.
   - Range Indicator Comments are inserted after the visual ruler.

4. Adds stronger prompt guardrails.
   - The prompt explicitly prints the locked range and target price at the top.
   - The prompt tells GPT not to widen or replace the range when report input supplies values.

5. Adds light output cleanup.
   - Removes assistant-style final offers such as “If you want, I can...”
   - Replaces seller-facing uses of “reconciliation” with “pricing basis.”
   - Aligns common generated range lines with `report_input` if old markdown is being previewed/exported.

## Install

Copy the patch files into the same paths in your local repo, replacing existing files.
Then run:

```cmd
streamlit run app/main.py
```

Go to Module 5, click **Build / Refresh Report Input**, confirm the range fields show `$660,000`, `$675,000`, and `$665,000`, then generate/download the report again.

## Still not included

Distance-from-subject calculation is not implemented yet. That remains the next valuation/competition engine task.
