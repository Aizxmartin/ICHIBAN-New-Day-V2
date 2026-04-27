"""Simple DOCX exporter for generated ICHIBAN report text."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Optional

from docx import Document


_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")


def _clean_inline_markdown(text: str) -> str:
    text = _BOLD_RE.sub(r"\1", text)
    return text.replace("__", "").strip()


def report_markdown_to_docx_bytes(report_text: str, title: Optional[str] = None) -> bytes:
    """
    Convert a markdown-like GPT report into a basic editable .docx file.

    This intentionally avoids Streamlit buttons, debug blocks, and app UI. The
    downloaded .docx should be the clean report artifact.
    """
    document = Document()

    if title:
        document.add_heading(title, level=0)

    for raw_line in (report_text or "").splitlines():
        line = raw_line.strip()

        if not line:
            continue

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

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
