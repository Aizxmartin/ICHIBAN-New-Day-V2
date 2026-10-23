# v19 Deployment Status

Status: partial push started from local patch files.

Committed to `dev`:

- `LOCAL_PATCH_SEPARATE_BBC_TARZAN_v19.md`
- `core/gpt_prompt_builder.py`

Remaining local v19 files to apply before server verification:

- `core/report_input_builder.py`
- `core/reporting/docx_exporter.py`
- `app/pages/5_Insight_Report.py`

Reason this status file exists:

The GitHub connector can create/update individual UTF-8 files, but it does not directly unpack and apply the local patch ZIP to the repository. The remaining files should be applied from the local patch ZIP before testing the server output.

Required verification after full apply:

1. BBC and Tarzan appear as separate reports in the same DOCX.
2. A page break separates BBC from Tarzan.
3. Recommended range remains valuation-based.
4. After-Active current list price uses the confirmed current price.
5. 10006 Boca current list price should be $649,000 if entered as confirmed current price.
6. After-Active delta should show -$16,000 against a $665,000 recommendation, not -$35,100.
7. No dollar delta should appear as the bottom of the range visual.
