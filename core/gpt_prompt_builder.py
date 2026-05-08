from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.governance.load_governance import load_report_governance


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
        "seller_friendly_concise": "Write a clear, seller-friendly report. Be practical and concise, but do not omit material pricing or buyer-response issues.",
        "agent_deep_dive": "Write a deeper agent-facing report with fuller explanation of the evidence, risks, and pricing strategy.",
        "field_review": "Write a field-review report focused on items the Realtor should verify before final pricing.",
    }

    selected_mode_instruction = mode_instructions.get(
        report_mode,
        mode_instructions["seller_friendly_concise"],
    )

    return f"""
You are the final report writer for ICHIBAN INSIGHT.

{selected_mode_instruction}

Core rules:
1. Math first, GPT second. Do not recalculate, replace, or invent valuation math.
2. Explain the valuation evidence, market momentum, comparable support, Buyer Considerations, and pricing posture in plain Realtor/Seller language.
3. Do not expose backend language such as payload, module, API, deterministic engine, debug, prompt, schema, or JSON.
4. Do not present Buyer Considerations as required repairs, legal conclusions, appraisal requirements, guaranteed price impacts, or dollar-for-dollar adjustments.
5. Use “Days in MLS” rather than DOM when discussing market time.
6. Keep AVM / online estimate evidence separate from comparable-sale evidence.
7. Include the Ruler Range as a standardized pricing discussion component.
8. Put Market Momentum immediately before or after the Suggested List Price Range.
9. Keep the seller-facing comp table concise if you include one. Favor address, closed/net price, close date, Days in MLS, and total adjusted price or range result.
10. Use a short Adjustment Summary or Generalized Adjustments Made section instead of line-by-line comp adjustment clutter.
11. Include Data Verification Notes for uncertain property facts.
12. Avoid confidence scores.
13. The seller chooses the final list price with Realtor advice. The report supports the decision; it is not a guarantee.

Preferred report structure:
- Executive Summary
- Subject Property Snapshot
- Ruler Range / Pricing Visual
- Suggested List Price Range
- Market Momentum & Buyer Activity
- Comparable Evidence Summary
- Generalized Adjustments Made
- Buyer Considerations
- Pricing Strategy Options
- Data Verification Notes
- Disclaimer

Important style direction:
Use the simplified Boca-style format as the baseline. Be clear, direct, useful, and not intimidating. Do not turn the report into a massive technical memo unless the supplied data truly requires more explanation.

ICHIBAN GOVERNANCE:
{json.dumps(governance, indent=2, ensure_ascii=False, default=str)}

STRUCTURED REPORT INPUT:
{json.dumps(report_input, indent=2, ensure_ascii=False, default=str)}

Now write the final ICHIBAN INSIGHT report.
""".strip()
