# ICHIBAN INSIGHT — Pre-API Diagnostic Layer Starter

This package adds the first diagnostic layer before extraction.

The purpose is simple:

> Do not run valuation extraction directly against raw uploads.  
> First classify the uploaded file and route it to the correct parser or fallback path.

## Files included

```text
core/pdf_diagnostics/
    __init__.py
    document_source_probe.py
    pdf_text_probe.py
    pdf_layout_probe.py
    xps_probe.py
    image_ocr_probe.py

diagnose_upload.py
streamlit_diagnostic_snippet.py
```

## Install packages

From your project folder:

```bash
py -m pip install pypdf pdfplumber
```

## Run from command line

```bash
py diagnose_upload.py "path/to/RealistReport.pdf"
```

For full JSON output:

```bash
py diagnose_upload.py "path/to/RealistReport.pdf" --json
```

## Expected output example

```json
{
  "file_type": "pdf",
  "text_found": true,
  "image_only": false,
  "coordinate_text_available": true,
  "xps_glyph_text_available": false,
  "likely_source": "realist_corelogic",
  "document_category": "B_searchable_pdf_coordinate_layout",
  "recommended_parser": "realist_pdf_coordinate_parser",
  "manual_fallback_required": false
}
```

## Streamlit integration

Use `streamlit_diagnostic_snippet.py` as the starting point for your subject intake page.

The diagnostic result should determine whether the app proceeds to:

```text
realist_pdf_coordinate_parser
generic_pdf_text_parser
generic_pdf_coordinate_parser
xps_glyph_parser
image_ocr_or_manual_subject_entry
manual_subject_entry
```

## Development rule

This is the correct sequence:

```text
1. Diagnose document
2. Select parser/fallback route
3. Extract fields
4. Show subject verification screen
5. Run valuation only after subject facts are verified
```
