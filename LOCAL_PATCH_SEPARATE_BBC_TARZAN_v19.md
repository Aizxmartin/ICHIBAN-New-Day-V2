# LOCAL PATCH — Separate BBC/Tarzan Reports v19

## Purpose
v19 keeps one DOCX package, but separates the output into two reports:

1. **PART 1 — BBC SELLER REPORT**
2. **PAGE BREAK**
3. **PART 2 — TARZAN ANALYTICAL REPORT**

This replaces the blended section-by-section format that used `Seller Point` followed immediately by `Tarzan support` inside every heading.

## Key rules

- BBC is the seller-facing report at the front of the DOCX.
- Tarzan is the detailed analytical backup report after the page break.
- Do not intermix BBC paragraphs and Tarzan support inside the same section.
- The Recommended Price Range and Recommended Price Logic Stack remain black-and-white and simple.
- The After-Active Price Logic Stack is inserted only in the Tarzan After-Active section, not at the top of the first-pass valuation report.

## Current-list-price safety fix

v19 adds a confirmed current list price input for After-Active review. It overrides stale/background prices for After-Active math only and does not change valuation.

Priority:
1. User-entered After-Active current list price
2. User-entered current list price
3. Additional-context current list price
4. Active subject row current price

If conflicting current prices are found, the After-Active stack notes the conflict and uses the confirmed/user-entered price.

## Range validation

The DOCX range visual now checks that:

`low <= recommended <= high` and `low < high`

If invalid values are detected, the exporter prints a clear data-check warning rather than displaying an impossible ruler.

## Changed files

- `core/gpt_prompt_builder.py`
- `core/report_input_builder.py`
- `core/reporting/docx_exporter.py`
- `app/pages/5_Insight_Report.py`
