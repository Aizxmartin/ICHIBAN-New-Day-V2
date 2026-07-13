from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.gpt_client import run_gpt_report
from core.gpt_prompt_builder import build_ichiban_report_prompt
from core.reporting.docx_exporter import report_markdown_to_docx_bytes
from core.reporting.report_payload_builder import build_report_payload


st.set_page_config(
    page_title="ICHIBAN - Insight Report",
    page_icon="📄",
    layout="wide",
)

st.title("Module 5 — ICHIBAN Insight Report")
st.subheader("Generate the final DOCX report from the locked Tarzan-first valuation handoff")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "to_dict") and hasattr(value, "columns"):
        try:
            return value.to_dict(orient="records")
        except Exception:
            return str(value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _load_json_file(path: str | Path) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_text(path: str | Path, text: str) -> Path:
    save_path = Path(path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(text or "", encoding="utf-8")
    return save_path


def _unwrap_engine_result(raw_result: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Module 4 stores a wrapper with engine metadata plus `engine_output`.
    The report payload builder needs the actual valuation engine output.
    """
    raw_result = raw_result or {}

    if isinstance(raw_result.get("engine_output"), dict):
        return raw_result["engine_output"], raw_result

    return raw_result, {
        "engine_status": raw_result.get("engine_status"),
        "engine_module": raw_result.get("engine_module"),
        "engine_function": raw_result.get("engine_function"),
    }


def _load_valuation_result() -> Dict[str, Any]:
    session_result = st.session_state.get("valuation_engine_result") or {}
    if session_result:
        return session_result

    saved_result = _load_json_file("data/valuation_engine_output.json")
    if saved_result:
        st.session_state["valuation_engine_result"] = saved_result
        return saved_result

    return {}


def _load_subject_profile(engine_output: Dict[str, Any]) -> Dict[str, Any]:
    session_subject = st.session_state.get("subject_profile") or {}
    if session_subject:
        return session_subject

    saved_subject = _load_json_file("data/verified_subject.json")
    if saved_subject:
        st.session_state["subject_profile"] = saved_subject
        return saved_subject

    return engine_output.get("subject_summary", {}) if isinstance(engine_output, dict) else {}


def _load_1004mc_summary(engine_output: Dict[str, Any]) -> Dict[str, Any]:
    session_1004mc = (
        st.session_state.get("one_hundred_four_mc_summary")
        or st.session_state.get("market_conditions_1004mc")
        or {}
    )
    if session_1004mc:
        return session_1004mc

    saved_1004mc = _load_json_file("data/verified_1004mc.json")
    if saved_1004mc:
        st.session_state["one_hundred_four_mc_summary"] = saved_1004mc
        st.session_state["market_conditions_1004mc"] = saved_1004mc
        return saved_1004mc

    return engine_output.get("market_conditions_1004mc", {}) if isinstance(engine_output, dict) else {}


def _money(value: Any) -> Any:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return value


def _build_prompt_ready_input(report_payload: Dict[str, Any], engine_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bridge the current server payload shape into the v19 prompt-builder shape.

    This is intentionally conservative: it uses the engine's selected comparable
    evidence as the locked price evidence when no separate final list range has
    been supplied yet.
    """
    engine_output = engine_output or {}
    report_payload = report_payload or {}

    selected_range = engine_output.get("selected_comparable_evidence_range", {}) or {}
    comp_stats = engine_output.get("comp_statistics", {}) or {}
    recommended_range = (report_payload.get("valuation_ranges", {}) or {}).get("recommended_list_price_range", {}) or {}

    low = _money(recommended_range.get("low") or selected_range.get("range_low"))
    high = _money(recommended_range.get("high") or selected_range.get("range_high"))
    target = _money(
        engine_output.get("recommended_list_price")
        or engine_output.get("suggested_list_price")
        or comp_stats.get("weighted_adjusted_average")
        or comp_stats.get("median_adjusted_price")
    )

    if target is not None and low is not None and high is not None:
        try:
            target = min(max(float(target), float(low)), float(high))
        except Exception:
            pass

    return {
        **report_payload,
        "report_mode": "combined_bbc_tarzan",
        "pricing_reconciliation": {
            "recommended_price_range_low": low,
            "recommended_price_range_high": high,
            "recommended_list_price": target,
            "pricing_source": "selected_comparable_evidence_range_when_no_final_market_entry_range_is_supplied",
        },
        "report_routing": {
            "after_active_overlay": False,
            "range_policy": [
                "Tarzan-first report generation uses the completed valuation engine output as the evidence handoff.",
                "GPT may explain supplied math but may not invent or recalculate valuation math.",
            ],
            "subject_market_snapshot": {},
        },
        "tarzan_first_handoff_controls": {
            "math_first_gpt_second": True,
            "gpt_may_explain_but_not_recalculate": True,
            "docx_renderer_must_preserve_report_boundaries": True,
        },
    }


# ---------------------------------------------------------------------
# Load current handoff
# ---------------------------------------------------------------------

raw_result = _load_valuation_result()
engine_output, engine_wrapper = _unwrap_engine_result(raw_result)
subject_profile = _load_subject_profile(engine_output)
market_inspection = st.session_state.get("market_inspection") or {}
one_hundred_four_mc_summary = _load_1004mc_summary(engine_output)

engine_ready = bool(engine_output and engine_output.get("engine_status") == "success")

c1, c2, c3 = st.columns(3)
c1.metric("Valuation engine ready", str(engine_ready))
c2.metric("Selected comps", str(engine_output.get("comp_rows_selected", "—") if engine_output else "—"))
c3.metric("Report mode", "combined_bbc_tarzan")

if not raw_result:
    st.warning("No valuation engine output found. Run Module 4 before generating the Insight Report.")
elif not engine_ready:
    st.warning("A valuation output was found, but it is not a successful engine result yet. Review Module 4 before generating the final report.")

with st.expander("Valuation engine wrapper", expanded=False):
    st.json(_json_safe(engine_wrapper))

with st.expander("Valuation engine output", expanded=False):
    st.json(_json_safe(engine_output))


# ---------------------------------------------------------------------
# Report controls
# ---------------------------------------------------------------------

st.divider()

user_notes = st.text_area(
    "Additional Realtor notes for this report",
    value=st.session_state.get("insight_report_user_notes", ""),
    height=140,
    help="Use this for verified property notes, showing feedback, listing-history notes, or repair caveats that Tarzan should consider in the final explanation.",
)
st.session_state["insight_report_user_notes"] = user_notes

estimated_days_until_market = st.number_input(
    "Estimated days until market",
    min_value=0,
    max_value=365,
    value=int(st.session_state.get("estimated_days_until_market", 0) or 0),
)
st.session_state["estimated_days_until_market"] = estimated_days_until_market

if engine_ready:
    report_payload = build_report_payload(
        engine_output=engine_output,
        subject_profile=subject_profile,
        market_inspection=market_inspection,
        user_notes=user_notes,
        estimated_days_until_market=int(estimated_days_until_market),
        one_hundred_four_mc_summary=one_hundred_four_mc_summary,
    )

    prompt_ready_input = _build_prompt_ready_input(report_payload, engine_output)
    prompt = build_ichiban_report_prompt(prompt_ready_input, report_mode="combined_bbc_tarzan")

    st.session_state["ichiban_report_payload"] = report_payload
    st.session_state["ichiban_report_prompt"] = prompt

    with st.expander("Structured report payload", expanded=False):
        st.json(_json_safe(report_payload))

    st.download_button(
        label="Download structured report payload JSON",
        data=json.dumps(_json_safe(report_payload), indent=2),
        file_name="ichiban_report_payload.json",
        mime="application/json",
    )

    st.download_button(
        label="Download report prompt TXT",
        data=prompt,
        file_name="ichiban_report_prompt.txt",
        mime="text/plain",
    )

    if st.button("Generate ICHIBAN Insight Report", type="primary"):
        with st.spinner("Generating final report text..."):
            report_text = run_gpt_report(prompt)

        st.session_state["ichiban_report_text"] = report_text
        saved_markdown_path = _save_text("outputs/ichiban_insight_report.md", report_text)
        st.success(f"Report text generated and saved to {saved_markdown_path}")

report_text = st.session_state.get("ichiban_report_text", "")

if report_text:
    st.markdown("## Report Preview")
    st.markdown(report_text)

    docx_bytes = report_markdown_to_docx_bytes(
        report_text,
        title="ICHIBAN Insight Report",
    )

    st.download_button(
        label="Download ICHIBAN Insight Report DOCX",
        data=docx_bytes,
        file_name="ICHIBAN_Insight_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    st.download_button(
        label="Download ICHIBAN Insight Report Markdown",
        data=report_text,
        file_name="ICHIBAN_Insight_Report.md",
        mime="text/markdown",
    )
