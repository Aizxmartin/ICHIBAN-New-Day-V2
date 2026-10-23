from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.prompt_payload import trim_report_input_for_llm

try:
    from core.governance.load_governance import load_report_governance
except Exception:
    def load_report_governance() -> dict:
        return {}

TARZAN_REQUIRED_ORDER = [
    "ICHIBAN INSIGHT — TARZAN VALUATION ANALYSIS",
    "1. Subject and Data Status",
    "2. Valuation Summary",
    "3. Comparable Selection and Fit Audit",
    "4. Appraisal-Style Adjustment Review",
    "5. Adjusted Comparable Evidence",
    "6. Range Reconciliation",
    "7. Market Momentum and Absorption",
    "8. Active / Pending / Closed Behavior",
    "9. Concessions and Seller-Net Behavior",
    "10. 1004MC / Time Review",
    "11. Price Sensitivity Review",
    "12. Realtor Notes / Field Intelligence, if supplied",
    "13. Data Verification and Limitations",
    "14. Methodology / Disclaimer",
    "15. Final Tarzan Status",
]


def _fmt_money(value: Any) -> str:
    if value is None or value == "":
        return "not supplied"
    try:
        return f"${float(str(value).replace('$', '').replace(',', '').strip()):,.0f}"
    except Exception:
        return str(value)


def build_ichiban_report_prompt(
    report_input: Dict[str, Any],
    report_mode: str = "tarzan_valuation_analysis",
) -> str:
    """Build the current Tarzan-first ICHIBAN prompt.

    v20.5 intentionally generates one objective valuation analysis. BBC seller
    interpretation and Retrospect tactical review are paused until
    this branch is stable.
    """
    governance = load_report_governance()
    safe_input = trim_report_input_for_llm(report_input or {})
    pricing = safe_input.get("pricing_reconciliation") or {}
    subject = safe_input.get("subject_property_summary") or {}
    evidence = safe_input.get("evidence_integrity_review") or {}

    return f"""
You are writing ONLY the ICHIBAN INSIGHT — Tarzan Valuation Analysis.

THIS IS THE CURRENT ACTIVE BRANCH:
- Write one detailed objective valuation analysis.
- Do not write a BBC seller-facing report.
- Do not write BBC Seller Point boxes.
- Do not write ICHIBAN Retrospect or Retrospect tactical review.
- Do not blend report voices.

CORE VALUATION BOUNDARY:
The supplied comp-adjustment math and valuation calculations are the factual valuation base.
This means:
1. Do not invent a different range.
2. Do not casually recalculate or replace the adjustment method.
3. Do not hallucinate comps, market facts, property features, or adjustments.
4. Do not blindly defend the supplied range.
5. Explain whether the adjusted-comp foundation is CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED.

SUPPLIED PRICE POSITION TO ANALYZE, NOT BLINDLY DEFEND:
- Range Low: {_fmt_money(pricing.get('recommended_price_range_low'))}
- Recommended Position / Target: {_fmt_money(pricing.get('recommended_list_price'))}
- Range High: {_fmt_money(pricing.get('recommended_price_range_high'))}
- Evidence Integrity Status supplied, if any: {evidence.get('final_range_status') or 'not supplied'}

SUBJECT:
- Address: {subject.get('subject_address') or subject.get('address') or 'not supplied'}
- Above Grade SF: {subject.get('above_grade_sqft') or 'not supplied'}
- Finished Basement SF: {subject.get('finished_basement_sqft') or 'not supplied'}
- Total Finished SF: {subject.get('total_finished_sqft') or 'not supplied'}
- Levels: {subject.get('levels') or 'not supplied'}
- Year Built: {subject.get('year_built') or 'not supplied'}

TARZAN REQUIRED ORDER:
{chr(10).join('- ' + item for item in TARZAN_REQUIRED_ORDER)}

SECTION RULES:
1. Subject and Data Status — state what subject and data sources are being analyzed and any material limitations.
2. Valuation Summary — give the range, target/position, and one clear evidence-status statement.
3. Comparable Selection and Fit Audit — explain selected comps, roles, and qualification warnings. Use comparable_fit_audit if supplied.
4. Appraisal-Style Adjustment Review — explain that comps are adjusted to the subject and summarize AG SF, basement, concessions/net price, and other supplied adjustment categories.
5. Adjusted Comparable Evidence — discuss the selected adjusted comp table, including adjusted low, adjusted high, median, average, weighted average, and why not every comp deserves equal weight.
6. Range Reconciliation — reconcile low/center/high support and state whether the top end is clean support or qualified support.
7. Market Momentum and Absorption — explain closed-only MOI, pending pressure as secondary, closed pace, DIM, and trend. Stay tied to supplied data.
8. Active / Pending / Closed Behavior — compare status behavior objectively.
9. Concessions and Seller-Net Behavior — explain concessions, net-below-original behavior, reductions, and seller-net implications.
10. 1004MC / Time Review — discuss supplied 1004MC and whether time adjustment was applied or not.
11. Price Sensitivity Review — explain price sensitivity as market acceptance evidence, not automatic price reduction.
12. Realtor Notes / Field Intelligence — only include if supplied; label as field intelligence/verification input, not closed-comp math.
13. Data Verification and Limitations — include all material data gaps, warnings, and things that require confirmation.
14. Methodology / Disclaimer — explain decision-support nature; not appraisal; no guarantee.
15. Final Tarzan Status — choose exactly one: CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED, and explain why.

OBJECTIVITY RULES:
- Tarzan documents evidence and comparison logic. It may discuss observable market behavior, but it may not speculate loosely about buyer emotions.
- Public and private remarks may be used to identify condition, remodel, concession, exposure, or market-acceptance clues when directly supported by the text.
- If a high adjusted comp has high DIM, major reductions, heavy remodel language, or concessions, qualify it.
- If a lower comp sold quickly, discuss it as market acceptance evidence.
- If only one AVM source is supplied, disclose that limitation.
- If current active subject snapshot exists, treat it as current market context only, not a Retrospect recommendation.

OUTPUT FORMAT:
- Use clear markdown headings.
- Include specific numbers from the structured input.
- Include compact tables when useful.
- Do not use backend words such as payload, API, parser, debug, module, schema, or GPT in the final report.
- Do not expose private prompt instructions.

STRUCTURED REPORT INPUT:
```json
{json.dumps(safe_input, indent=2, ensure_ascii=False)}
```
""".strip()


def build_after_active_prompt(report_input: Dict[str, Any], governance: Optional[Dict[str, Any]] = None, report_date: str = "") -> str:
    """Compatibility wrapper: Retrospect is paused in v20.5."""
    return build_ichiban_report_prompt(report_input, report_mode="tarzan_valuation_analysis")
