"""DOCX exporter for generated ICHIBAN report text.

Tarzan-first rendering rule:
The renderer must preserve structural handoff intent from the report prompt.
It may clean markdown for readability, but it must not silently flatten report
boundaries such as the BBC/Tarzan page break.
"""

from __future__ import annotations

from io import BytesIO
import re
from typing import Optional

from docx import Document


_BOLD_RE = re.compile(r"\*\*(.*?)\*")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _clean_inline_markdown(text: str) -> str:
    text = _BOLD_RE.sub(r"\1", text)
    return text.replace("__", "").strip()


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _parse_table_row(line: str) -> list[str]:
    return [_clean_inline_markdown(cell.strip()) for cell in line.strip().strip("|").split("|")]


def _add_markdown_table(document: Document, rows: list[list[str]]) -> None:
    if not rows:
        return

    normalized_rows = [row for row in rows if row]
    if not normalized_rows:
        return

    max_cols = max(len(row) for row in normalized_rows)
    table = document.add_table(rows=0, cols=max_cols)
    table.style = "Table Grid"

    for row_index, row_values in enumerate(normalized_rows):
        cells = table.add_row().cells
        for col_index in range(max_cols):
            cells[col_index].text = row_values[col_index] if col_index < len(row_values) else ""
        if row_index == 0:
            for cell in cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True


def _flush_table(document: Document, pending_table: list[list[str]]) -> None:
    if pending_table:
        _add_markdown_table(document, pending_table)
        pending_table.clear()


def report_markdown_to_docx_bytes(report_text: str, title: Optional[str] = None) -> bytes:
    """
    Convert a markdown-like GPT report into an editable .docx file.

    Required structural controls:
    - "PAGE BREAK" creates a real page break rather than visible filler text.
    - Markdown tables are preserved as editable Word tables.
    - Headings, bullets, and numbered lists remain editable text.
    """
    document = Document()

    if title:
        document.add_heading(title, level=0)

    pending_table: list[list[str]] = []

    for raw_line in (report_text or "").splitlines():
        line = raw_line.strip()

        if not line:
            _flush_table(document, pending_table)
            continue

        if line.upper() == "PAGE BREAK":
            _flush_table(document, pending_table)
            document.add_page_break()
            continue

        if _is_table_row(line):
            # Skip markdown separator rows such as | --- | --- |.
            if not _TABLE_SEPARATOR_RE.match(line):
                pending_table.append(_parse_table_row(line))
            continue

        _flush_table(document, pending_table)

        if line.startswith("### "):
            document.add_heading(_clean_inline_markdown(line[4:]), level=3)
        elif line.startswith("## "):
            document.add_heading(_clean_inline_markdown(line[3:]), level=2)
        elif line.startswith("# "):
            document.add_heading(_clean_inline_markdown(line[2:]), level=1)
        elif line.startswith(("- ", "• ")):
            document.add_paragraph(_clean_inline_markdown(line[2:]), style="List Bullet")
        elif re.match(r"^\d+\.\s+", line):
            document.add_paragraph(_clean_inline_markdown(re.sub(r"^\d+\.\s+", "", line)), style="List Number")
        else:
            document.add_paragraph(_clean_inline_markdown(line))

    _flush_table(document, pending_table)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
