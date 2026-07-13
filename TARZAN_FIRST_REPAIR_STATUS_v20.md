# Tarzan-First Repair Status v20

Status: controlled repair branch now includes the first renderer fix and the missing Module 5 report-generation page.

Branch:

- `agent/tarzan-first-renderer-handoff-controls`

Server ZIP reviewed:

- Uploaded server package: `ICHIBAN-New-Day-V2-dev.zip`
- ZIP root comment / source commit: `785a36fa322dab481df73025a2989c291523e9a8`
- The server file set matches the June 14 `dev` baseline with Modules 1 through 4 only.

Confirmed server structure:

- Present: `core/gpt_prompt_builder.py`
- Present: `core/reporting/report_payload_builder.py`
- Present: `core/reporting/docx_exporter.py`
- Present: `app/pages/4_valuation_run.py`
- Missing from server: `app/pages/5_Insight_Report.py`
- Missing by old v19 name: `core/report_input_builder.py`

Interpretation:

The server can currently load verified subject data, load normalized market data, run the valuation engine, save `data/valuation_engine_output.json`, and download that JSON from Module 4. It does not yet provide a Streamlit page that turns the valuation handoff into the final Insight Report prompt, GPT report text, and DOCX export.

Patches applied in this branch:

1. `core/reporting/docx_exporter.py`
   - `PAGE BREAK` is now treated as a real Word page break instead of visible report text.
   - Markdown tables are converted into editable Word tables instead of plain paragraphs.
   - Headings, bullets, and numbered lists remain editable Word content.
   - The exporter now states a Tarzan-first rendering rule: the renderer may clean markdown, but it must not silently flatten report boundaries.

2. `app/pages/5_Insight_Report.py`
   - Adds the missing report-generation page after Module 4.
   - Loads the valuation engine output from session state or `data/valuation_engine_output.json`.
   - Unwraps Module 4's `engine_output` wrapper before building the report handoff.
   - Uses the current server's `core/reporting/report_payload_builder.py` as the structured handoff builder.
   - Bridges that payload into the v19 `build_ichiban_report_prompt` format.
   - Generates final report text through `run_gpt_report(prompt)`.
   - Exports both Markdown and DOCX.
   - Keeps the default report mode as `combined_bbc_tarzan` because that is the current v19 prompt standard, but this push does not add After Review or Retrospect behavior.

Why this matters:

The previous v19 status note said several local v19 files remained to be applied before server verification. The server ZIP clarified that `report_input_builder.py` is not the current filename; the live server uses `report_payload_builder.py`. The missing practical link is a Streamlit Module 5 page that creates the final report from the valuation result.

Not included in this push:

- No valuation math changes.
- No After Review changes.
- No Retrospect changes.
- No new BBC doctrine or BBC expansion beyond preserving the existing v19 combined package boundary.
- No production server restart or SSH deployment from this environment.

Required verification:

1. Merge or test this branch on the server.
2. Restart Streamlit if required so Module 5 appears.
3. Run Module 4 and confirm `data/valuation_engine_output.json` is created.
4. Open Module 5 and confirm it loads the successful valuation result.
5. Download the prompt TXT and inspect whether the locked Tarzan-first values are present.
6. Generate the report.
7. Download the DOCX.
8. Confirm no literal `PAGE BREAK` text appears.
9. Confirm the BBC/Tarzan boundary is a real page break.
10. Confirm comparable evidence tables render as editable Word tables.
11. Confirm the output does not drift into After Review or Retrospect.

Next repair targets:

1. Test Module 5 on the server with a known Boca regression case.
2. Add a small regression artifact or checklist that validates: Tarzan calculation -> structured handoff -> prompt -> DOCX renderer -> final document.
3. Decide whether the report page should display only Tarzan-first controls during repair mode, even though the current v19 package is still named `combined_bbc_tarzan`.
