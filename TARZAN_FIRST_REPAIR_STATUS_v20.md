# Tarzan-First Repair Status v20

Status: first controlled repair branch opened for renderer and handoff preservation.

Branch:

- `agent/tarzan-first-renderer-handoff-controls`

Initial patch applied:

- `core/reporting/docx_exporter.py`

Purpose:

The current Tarzan-first repair risk is not only valuation logic. The report handoff can be correct while the final DOCX flattens or misrepresents report structure. This patch begins the repair at the renderer layer by preserving structural handoff instructions in the generated Word document.

What changed:

1. `PAGE BREAK` is now treated as a real Word page break instead of visible report text.
2. Markdown tables are converted into editable Word tables instead of plain paragraphs.
3. Headings, bullets, and numbered lists remain editable Word content.
4. The exporter now states a Tarzan-first rendering rule: the renderer may clean markdown, but it must not silently flatten report boundaries.

Why this matters:

The v19 prompt already asks for one DOCX package with separate report sections. Without a real renderer control, the output can still appear blended or unfinished even when the prompt and analysis are correct.

Not included in this first push:

- No After Review or Retrospect changes.
- No BBC logic changes beyond preserving the existing report boundary already required by v19.
- No valuation math changes.
- No server deployment from this environment.

Next repair targets:

1. Add or restore the structured report-input handoff file if the local patch version is available.
2. Verify where `app/pages/5_Insight_Report.py` currently lives or whether the app page was renamed.
3. Add a regression artifact that proves: Tarzan calculation -> structured handoff -> prompt -> DOCX renderer -> final document.
4. Confirm server deployment path outside GitHub, because this environment can push repository changes but cannot SSH or restart the production server.

Required verification:

1. Generate a combined ICHIBAN DOCX.
2. Confirm the BBC/Tarzan boundary is a real page break.
3. Confirm comparable evidence tables render as editable Word tables.
4. Confirm no literal `PAGE BREAK` text appears in the final document.
5. Confirm the output does not drift into After Review, Retrospect, or non-requested BBC expansion during Tarzan-first repair testing.
