# ICHIBAN Priority Report Refinement Patch

This patch implements the highest-priority seller-facing report refinements discussed after the first working Module 5 output.

## Implemented now

1. **Locked seller-facing report order**
   - Recommended Range + Ruler
   - Executive Summary bullets
   - Comparable Evidence table
   - How the Value Was Determined / Generalized Adjustments
   - AVM / Online Benchmarks
   - Current Competition Check
   - Market Momentum
   - Buyer Considerations
   - Strategy / Launch Notes
   - Disclaimer

2. **DOCX Ruler Range visual**
   - Adds a structured Word-table ruler before the narrative body.
   - Uses the standard labels: Market Support -> Target Position -> Market Opportunity.
   - Adds Range Indicator Comments.

3. **Pricing discipline**
   - Keeps the broad selected-comp evidence range separate from the narrower Recommended Market Entry Range.
   - If the Realtor does not manually enter a recommended range, the report input builder creates a conservative draft range from the selected comp center evidence.
   - For the 10006 Boca test JSON, this produces a draft range of $660,000-$675,000 and target position of $665,000, pending Realtor review.

4. **Prompt discipline**
   - Prevents seller-facing references to GPT/API/backend language.
   - Avoids the word “reconciliation” in seller-facing sections.
   - Separates Current Competition Check from Market Momentum.
   - Requires distance-from-subject to be included only when supplied; distances must not be invented.
   - Prevents final reports from ending with “If you want, I can...” style assistant language.

5. **Module 5 UI note**
   - Adds a visible locked-report-standard expander for review.
   - DOCX export now passes `report_input` into the exporter so the visual Ruler Range can be created from structured data.

## Files included

- app/pages/5_Insight_Report.py
- core/gpt_prompt_builder.py
- core/report_input_builder.py
- core/reporting/docx_exporter.py
- core/reporting/__init__.py
- PRIORITY_REPORT_REFINEMENT_NOTES.md

## Still later / not in this patch

- Full distance-from-subject calculation engine.
- Deeper Current Competition / Momentum engine using a separate market activity file.
- Native Word chart/image-based ruler instead of Word-table ruler.
- Fully styled seller-facing DOCX template with branding, page headers, and polished tables.
