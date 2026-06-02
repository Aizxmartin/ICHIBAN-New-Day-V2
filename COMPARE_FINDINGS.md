# ICHIBAN Current Merge Patch — 2026-05-11

This patch combines the most current local Module 3 two-file market intake with the missing Module 5 report handoff files.

## Comparison finding

- The GitHub `dev` zip and the local working copy are the same except for actual content changes in `app/pages/3_market_data_intake.py`; the other modified-looking files are line-ending differences.
- The local working copy is on branch `market-intake-two-file-workflow`.
- The local working copy contains prior generated report artifacts in `data/`, including `data/ichiban_insight_report.md`, but it does not currently have `app/pages/5_Insight_Report.py` installed.
- The report-generation code exists in the local patch folder `ichiban_gpt_report_handoff_patch_v1/ichiban_gpt_handoff_patch/` and on the GitHub branch `report-template-v1`.

## Files included

```text
app/pages/3_market_data_intake.py
app/pages/5_Insight_Report.py
core/gpt_prompt_builder.py
core/report_input_builder.py
core/governance/ICHIBAN_GPT_Supplemental_Rules_v1.json
core/governance/ICHIBAN_Insight_Report_Governance_v2.json
docs/GPT_REPORT_HANDOFF_PATCH_README.md
```

## Install

Copy these files into the matching locations in your repo while on `market-intake-two-file-workflow`.

Then run:

```cmd
streamlit run app/main.py
```

You should see Module 5 — ICHIBAN Insight Report.

## Notes

The added Module 5 restores the report handoff/page and includes markdown download plus a basic DOCX export using the existing `core/reporting/docx_exporter.py`. This does not yet recreate every polished Word-table/ruler formatting detail from the Boca sample report, but it restores the missing report generation path and gives us a clean place to improve DOCX formatting next.
