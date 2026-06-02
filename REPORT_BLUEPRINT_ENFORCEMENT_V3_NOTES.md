# ICHIBAN Report Blueprint Enforcement Patch v3

## Purpose

This patch enforces the highest-priority ICHIBAN seller-facing report rules:

1. Recommended Range + Ruler appears first.
2. Ruler labels no longer use “Market Opportunity.”
3. The high-end marker is now “High-Risk Stretch.”
4. Recommended Market Entry Range stays narrower than the selected-comp evidence range.
5. Existing/stale `report_input.json` and saved markdown reports no longer override current valuation output.
6. Default form values do not become a manual pricing override unless the Realtor explicitly checks the manual override box.
7. DOCX export aligns the report body with the current report-input pricing values.
8. The report prompt reinforces evidence-supported judgment and prevents unsupported AI-style drift.

## Expected Boca Test Output

For the current 10006 Boca valuation JSON, unless the Realtor manually overrides pricing:

- Recommended Market Entry Range: `$660,000–$675,000`
- Target Position: `$665,000`
- Market Support: `$625,315`
- High-Risk Stretch marker: `$730,250`

## New Ruler Labels

Use:

- Market Support
- Lower Entry
- Target Position
- Strategic Upper
- High-Risk Stretch

Do not use:

- Market Opportunity
- Upside Opportunity
- Maximum Value
- Top Dollar

## Install

Copy these files into the same relative paths in the local repo:

- `app/pages/5_Insight_Report.py`
- `core/report_input_builder.py`
- `core/gpt_prompt_builder.py`
- `core/reporting/docx_exporter.py`
- `core/reporting/__init__.py`

Then run:

```cmd
streamlit run app/main.py
```

In Module 5:

1. Leave “Manually override the auto-drafted recommended range” unchecked.
2. Click “Build / Refresh Report Input.”
3. Confirm Active Report Pricing shows `$660,000`, `$665,000`, `$675,000` for the Boca test.
4. Generate a fresh report.
5. Download DOCX.

## Important

If the page warns that a saved markdown report does not match the current pricing/version, generate a fresh report before downloading the DOCX. This prevents old `$665,000–$695,000` body text from carrying forward.
