from __future__ import annotations

import copy
from typing import Any, Dict, List

MAX_TEXT_PREVIEW_CHARS = 1200
MAX_NOTE_CHARS = 6000
MAX_COMPS = 12


def _trim_text(value: Any, limit: int = MAX_NOTE_CHARS) -> Any:
    if not isinstance(value, str):
        return value
    return value if len(value) <= limit else value[:limit] + "\n...[trimmed for GPT prompt budget]"


def _trim_support_files(items: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    trimmed = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        trimmed.append({
            "filename": item.get("filename"),
            "suffix": item.get("suffix"),
            "content_type": item.get("content_type"),
            "size_bytes": item.get("size_bytes"),
            "tabular_summary": item.get("tabular_summary"),
            "text_preview": _trim_text(item.get("text_preview") or "", MAX_TEXT_PREVIEW_CHARS),
            "note": _trim_text(item.get("note") or "", MAX_TEXT_PREVIEW_CHARS),
            "error": item.get("error"),
        })
    return trimmed


def trim_report_input_for_llm(report_input: Dict[str, Any]) -> Dict[str, Any]:
    """Return a smaller, safer prompt payload while preserving decision-critical facts."""
    data = copy.deepcopy(report_input or {})

    for key in ("selected_adjusted_comps", "all_scored_comps_preview"):
        if isinstance(data.get(key), list) and len(data[key]) > MAX_COMPS:
            data[key] = data[key][:MAX_COMPS]

    current_inputs = data.get("current_after_active_inputs")
    if isinstance(current_inputs, dict):
        current_inputs["additional_support_files"] = _trim_support_files(current_inputs.get("additional_support_files"))
        for k, v in list(current_inputs.items()):
            current_inputs[k] = _trim_text(v)

    notes = data.get("additional_notes_provided")
    if isinstance(notes, dict):
        notes["support_files"] = _trim_support_files(notes.get("support_files"))
        if isinstance(notes.get("categories"), list):
            for item in notes["categories"]:
                if isinstance(item, dict) and "notes" in item:
                    item["notes"] = _trim_text(item.get("notes"))

    for key in ("realtor_notes", "buyer_consideration_notes", "listing_history_notes", "showing_feedback_notes"):
        if key in data:
            data[key] = _trim_text(data.get(key))

    data["prompt_payload_trimmed"] = True
    return data
