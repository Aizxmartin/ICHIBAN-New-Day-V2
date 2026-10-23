# Current Repair Notes — 2026-07-21

## Module 3 intake clarity

- Removed the top-of-page `1004MC / Competition Market File search rule` JSON expander.
- Renamed the spreadsheet input to `Competition Market File` so it is not confused with the separate `1004MC Summary PDF`.
- Moved concise search guidance next to the optional Competition Market File workflow.
- Clarified the three distinct inputs:
  1. Comparable Sales / Valuation File
  2. Competition Market File
  3. 1004MC Summary PDF

## 1004MC browser-print PDF fallback

- Added `packages.txt` with `tesseract-ocr` for Streamlit deployment.
- Increased first-page rendering from 2.2x to 3.0x before OCR.
- High-confidence OCR now requires all 18 core Year-1 1004MC values before validation can pass.
- Confirmed the supplied Matrix browser-print PDF routes through `parsed_1004mc_ocr_table` and reproduces the visible Year-1 table values.
