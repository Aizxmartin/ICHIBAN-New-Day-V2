from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from core.governance.load_governance import load_report_governance
except Exception:  # Governance files may not be installed in older local copies yet.
    def load_report_governance() -> dict:
        return {}


LOCKED_REPORT_ORDER = [
    "Recommended Range + Ruler",
    "Executive Summary bullets",
    "Comparable Evidence table",
    "How the Value Was Determined / Generalized Adjustments",
    "AVM / Online Benchmarks",
    "Current Competition Check",
    "Market Momentum",
    "Buyer Considerations",
    "Strategy / Launch Notes",
    "Disclaimer",
]


def build_ichiban_report_prompt(
    report_input: Dict[str, Any],
    governance: Optional[Dict[str, Any]] = None,
    report_mode: str = "seller_friendly_concise",
) -> str:
    """
    Build the GPT prompt for the ICHIBAN final report.

    This prompt is deliberately separate from the API client so the Streamlit app
    can preview and debug the prompt without making an API call.
    """
    governance = governance or load_report_governance()

    mode_instructions = {
        "seller_friendly_concise": (
            "Write a clear, seller-friendly report. Be practical and concise, "
            "but do not omit material pricing, competition, or buyer-response issues."
        ),
        "agent_deep_dive": (
            "Write a deeper agent-facing report with fuller explanation of the evidence, "
            "risks, market competition, and pricing strategy."
        ),
        "field_review": (
            "Write a field-review report focused on items the Realtor should verify before final pricing."
        ),
    }

    selected_mode_instruction = mode_instructions.get(
        report_mode,
        mode_instructions["seller_friendly_concise"],
    )

    locked_order_text = "\n".join(f"{i + 1}. {section}" for i, section in enumerate(LOCKED_REPORT_ORDER))

    pricing = report_input.get("pricing_reconciliation", {}) if isinstance(report_input, dict) else {}
    ruler = report_input.get("ruler_range", {}) if isinstance(report_input, dict) else {}

    def _fmt_money(value: Any) -> str:
        if value is None or value == "":
            return "not supplied"
        try:
            return f"${float(str(value).replace('$', '').replace(',', '').strip()):,.0f}"
        except Exception:
            return str(value)

    locked_price_values = (
        f"Recommended Market Entry Range: {_fmt_money(pricing.get('recommended_price_range_low'))} — "
        f"{_fmt_money(pricing.get('recommended_price_range_high'))}\n"
        f"Target Position / Strategic List Posture: {_fmt_money(pricing.get('recommended_list_price'))}\n"
        f"Broad Ruler Evidence Context: {_fmt_money(ruler.get('ruler_low'))} — {_fmt_money(ruler.get('ruler_high'))} (upper marker is High-Risk Stretch unless evidence supports it)"
    )

    return f"""
You are the final report writer for ICHIBAN INSIGHT.

{selected_mode_instruction}

LOCKED PRICING VALUES — USE THESE EXACTLY WHEN SUPPLIED:
{locked_price_values}

Do not widen, raise, or replace the Recommended Market Entry Range unless the structured report input explicitly supplies a different Realtor-entered range. The broad Ruler evidence context is not the recommended list range.

NON-NEGOTIABLE REPORT ORDER:
{locked_order_text}

Core rules:
1. Math first, narrative second. Do not recalculate, replace, or invent valuation math.
2. Do not expose backend language such as payload, module, API, deterministic engine, debug, prompt, schema, JSON, or GPT.
3. Do not use the word "reconciliation" in the seller-facing report. Use "How the Value Was Determined" or "Pricing Basis" instead.
4. The Ruler Range must be at the top with the Recommended Market Entry Range. The Ruler is a pricing conversation visual, not a guarantee.
5. Use these standard Ruler labels: Market Support → Lower Entry → Target Position → Strategic Upper → High-Risk Stretch. Do not use “Market Opportunity” on the ruler.
6. Include Range Indicator Comments after the Ruler. Explain Market Support, Target Position, Strategic Upper, and High-Risk Stretch positioning.
7. Keep the broad selected-comp evidence range separate from the narrower Recommended Market Entry Range.
8. Do not turn the highest adjusted comp into an automatic list price. Treat the upper evidence marker as High-Risk Stretch unless updates, unusually low inventory, superior features, or strong early buyer response justify it.
9. If report_input supplies a recommended range, use it exactly in every section that references the recommended range. Do not create a higher or wider range unless the report_input explicitly supports it.
10. If the recommended range is auto-drafted, describe it as a practical starting lane requiring Realtor review, not as a guaranteed conclusion.
11. Keep AVM / online estimate evidence separate from closed comparable evidence.
12. Current Competition Check and Market Momentum are different sections:
    - Current Competition Check = active/current buyer alternatives and launch-price risk.
    - Market Momentum = market speed/rhythm, absorption, pending pressure, Days in MLS, and buyer activity.
13. Active, Coming Soon, and Pending listings influence pricing advice, launch posture, and first-week strategy; they do not create the closed-comp value range.
14. Use “Days in MLS” rather than DOM.
15. Include distance from subject for comps or competition only when distance data is supplied. Do not invent distances.
16. Keep the seller-facing comparable table concise: address, distance if available, closed/net price, close date, Days in MLS, and total adjusted price/result.
17. Use “How the Value Was Determined” or “Generalized Adjustments” instead of line-by-line adjustment spreadsheets.
18. Buyer Considerations are not required repairs, legal conclusions, appraisal requirements, guaranteed price impacts, or dollar-for-dollar adjustments.
19. Include Data Verification Notes only for uncertain property facts that materially affect pricing, buyer confidence, or marketing.
20. Avoid confidence scores.
21. The seller chooses the final list price with Realtor advice. The report supports decision-making; it is not a guarantee.
22. Do not end with offers such as “If you want, I can...” The report must read like a finished deliverable.

ICHIBAN philosophy:
- Intelligence must be earned through evidence.
- This is data-supported strategic market positioning, not AI guessing.
- The math supports the narrative; the narrative explains the math; momentum and current competition validate or caution the positioning.
- Caveats are part of professional intelligence when data is thin, mixed, or condition-dependent.

Required section guidance:
- Recommended Range + Ruler: include the recommended range, strategic list posture/price if supplied, Ruler labels, and Range Indicator Comments. The upper ruler marker must not be called Market Opportunity.
- Executive Summary bullets: keep concise and seller-friendly.
- Comparable Evidence table: closed comparable evidence only; include distance only if supplied.
- How the Value Was Determined: explain above-grade space, basement contribution, condition/updates, layout/features, concessions/net price, and time adjustments if supplied.
- AVM / Online Benchmarks: use as secondary context only.
- Current Competition Check: discuss current active/pending alternatives and limitations of the data.
- Market Momentum: discuss market speed using Days in MLS, pending pressure, absorption/months supply, and current trend evidence.
- Buyer Considerations: use the Buyer Considerations label, not cost-to-cure as the section title.
- Strategy / Launch Notes: focus on preparation, first-week posture, feedback/reprice trigger, and pricing risk.
- Disclaimer: concise, professional, and seller-facing.

Important style direction:
Use the simplified Boca-style report as the baseline: confident, clear, seller-friendly, visually organized, and not intimidating. Keep the report tight unless supplied data requires more explanation.

ICHIBAN GOVERNANCE:
{json.dumps(governance, indent=2, ensure_ascii=False, default=str)}

STRUCTURED REPORT INPUT:
{json.dumps(report_input, indent=2, ensure_ascii=False, default=str)}

Now write the final ICHIBAN INSIGHT report in the locked section order. Do not include a closing offer, assistant note, or any “If you want...” language.
""".strip()
