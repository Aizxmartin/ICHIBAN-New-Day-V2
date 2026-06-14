from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from core.governance.load_governance import load_report_governance
except Exception:  # Governance files may not be installed in older local copies yet.
    def load_report_governance() -> dict:
        return {}


BBC_REPORT_ORDER = [
    "PART 1 — BBC SELLER REPORT",
    "1. Recommended Price Position",
    "2. Why This Price Makes Sense",
    "3. Current Market Reality",
    "4. Buyer Confidence / Property Presentation",
    "5. Pricing Strategy",
    "6. What We Will Watch",
    "7. Bottom Line Recommendation",
]

TARZAN_REPORT_ORDER = [
    "PART 2 — TARZAN ANALYTICAL REPORT",
    "1. Valuation Summary",
    "2. Recommended Price Logic Stack",
    "3. Comparable Evidence",
    "4. Comp Adjustment Summary",
    "5. Market Momentum",
    "6. Active / Pending / Closed Price Behavior",
    "7. Closed Concessions and Net Price Review",
    "8. 1004MC / Time Adjustment Review",
    "9. Price Sensitivity & Seller Net Behavior",
    "10. Market Acceptance / Repositioning Review",
    "11. After-Active Property Review — Tactical Overlay, if applicable",
    "12. Additional Notes Provided",
    "13. Tarzan Data Verification / Backup Notes",
    "14. Methodology / Disclaimer",
]

COMBINED_ORDER = [
    *BBC_REPORT_ORDER,
    "PAGE BREAK",
    *TARZAN_REPORT_ORDER,
]


def _fmt_money(value: Any) -> str:
    if value is None or value == "":
        return "not supplied"
    try:
        return f"${float(str(value).replace('$', '').replace(',', '').strip()):,.0f}"
    except Exception:
        return str(value)


def _select_order(report_mode: str) -> list[str]:
    # v19 keeps one DOCX package but separates the two reports:
    # BBC seller-facing report first, then Tarzan analytical report after a page break.
    return COMBINED_ORDER


def build_ichiban_report_prompt(
    report_input: Dict[str, Any],
    governance: Optional[Dict[str, Any]] = None,
    report_mode: str = "combined_bbc_tarzan",
) -> str:
    """
    Build the GPT prompt for the ICHIBAN final report.

    v19 locks the single BBC/Tarzan Seller Advisory Package standard:
    - BBC is a separate seller-facing report at the front of the DOCX.
    - Tarzan is a separate analytical support report after a page break.
    - They live in the same .docx package but must not be blended section-by-section.
    """
    governance = governance or load_report_governance()
    report_input = report_input or {}

    # Single-report standard: legacy modes are accepted only for stale saved JSON, then
    # normalized to the BBC/Tarzan Seller Advisory Report.
    report_mode = "combined_bbc_tarzan"
    selected_mode_instruction = (
        "Write the single standard ICHIBAN DOCX package as TWO SEPARATE REPORTS in this order: "
        "PART 1 — BBC SELLER REPORT first, then PAGE BREAK, then PART 2 — TARZAN ANALYTICAL REPORT. "
        "Do not intermix BBC paragraphs and Tarzan support inside the same section. "
        "BBC is the seller-facing advisory report. Tarzan is the detailed analytical backup report. "
        "After-Active, listing-history, and Realtor-note reviews belong in Tarzan unless a short seller-facing summary is needed in BBC."
    )
    locked_order = _select_order(report_mode)
    locked_order_text = "\n".join(f"{i + 1}. {section}" for i, section in enumerate(locked_order))

    pricing = report_input.get("pricing_reconciliation", {}) if isinstance(report_input, dict) else {}
    report_routing = report_input.get("report_routing", {}) if isinstance(report_input, dict) else {}
    after_active_overlay = bool(report_routing.get("after_active_overlay"))
    range_policy = report_routing.get("range_policy") or []
    subject_market_snapshot = report_routing.get("subject_market_snapshot") or {}
    report_date = report_input.get("report_date") or str(report_input.get("created_at") or "the report date")[:10]
    low = _fmt_money(pricing.get("recommended_price_range_low"))
    high = _fmt_money(pricing.get("recommended_price_range_high"))
    target = _fmt_money(pricing.get("recommended_list_price"))

    source_sentence = (
        "Based on the available evidence, comparable property data, online benchmarks, current competition, "
        "market momentum, and Realtor-provided property information available as of this report date, "
        "the recommended market-entry range is selected because it best balances closed-sale support, "
        "buyer expectations, current inventory, property condition, and likely negotiation leverage."
    )

    after_active_instruction = ""
    if after_active_overlay:
        after_active_instruction = f"""
AFTER-ACTIVE PROPERTY REVIEW OVERLAY:
This property appears to be already exposed to the market or has current showing/market feedback. Do not treat this as only a pre-list valuation.
Separate these layers clearly:
{chr(10).join("- " + str(item) for item in range_policy)}
Subject market snapshot detected for routing:
{json.dumps(subject_market_snapshot, indent=2, ensure_ascii=False, default=str)}

When this overlay is active:
- The Closed-Comp Supported Range remains evidence, but current market response may supersede it for next-step advice.
- If current list price is above the supported range, explain repositioning pressure plainly.
- If current list price is below the supported range but buyer activity is weak, explain that the issue may be marketability, presentation, incentives, active competition, condition, unfinished work, payment pressure, or an adjustment-model caveat.
- Never claim the property should chase a higher number just because closed-comp math supports it. Translate value into showing conversion and buyer urgency.
- In BBC, include only a short seller-facing tactical note if After-Active materially changes the advice. Put the full After-Active Property Review and After-Active Price Logic Stack in Tarzan only.
- If Listing History / Relist Notes are supplied, discuss cumulative exposure separately from current ListingID Days in MLS. Do not call the listing fresh if a prior expired/withdrawn ListingID shows meaningful prior exposure.
""".strip()

    return f"""
You are the final report writer for ICHIBAN INSIGHT.

{selected_mode_instruction}

REPORT DATE:
Use this report date in the report: {report_date}

LOCKED PRICE VALUES — USE EXACTLY WHEN SUPPLIED:
Recommended Market Entry Range: {low} — {high}
Recommended Position: {target}

LOCKED BBC/TARZAN PRICE VISUAL RULE:
The DOCX exporter inserts the locked black-and-white Recommended Price Range visual near the top of the BBC report. Do not create a second range table, colored bar, five-column ruler, or alternate price visual in the narrative. The permanent visual uses only: Bottom of Range | Recommended Position | Top of Range, followed by the black-and-white tick-mark ruler and Preferred Seller Position / Notes line.

LOCKED PRICING LOGIC STACK RULE:
The DOCX exporter inserts the simple black-and-white Recommended Price Logic stacked line-item table from STRUCTURED REPORT INPUT near the top package/BBC area. Do not create a graphic, chart, colored visual, chalkboard visual, or duplicate pricing stack in the narrative. Treat the stack as a plain-text worksheet: each review layer gets its own line item, $0 is shown when no separate adjustment is applied, and comp-grid adjustments remain separate from market/review adjustments. If After-Active is triggered, the After-Active Price Logic Stack is inserted only in the Tarzan After-Active section. Do not mix the After-Active overlay into first-pass valuation logic.

SEPARATE REPORTS RULE:
The DOCX must read as two separate reports in one file. Use the exact headings “PART 1 — BBC SELLER REPORT” and “PART 2 — TARZAN ANALYTICAL REPORT.” BBC should be concise, seller-facing, and advisory. Tarzan should be detailed, data-backed, and analytical. Do not write “Seller Point / Tarzan support” pairs inside every section. That blended format is not allowed in v19.

REPORT SOURCE SENTENCE — USE THIS IDEA NEAR THE BEGINNING:
{source_sentence}

NON-NEGOTIABLE REPORT ORDER FOR THIS MODE:
{locked_order_text}

RANGE CONFIDENCE RULE:
Once ICHIBAN selects the Recommended Range, the BBC and Tarzan sections must explain why that range is reasonable based on information available as of the report date. Do not argue for a higher or lower range inside the report unless the selected range itself has been changed. Explain risks, buyer-confidence concerns, market resistance, and repositioning triggers as support for strategy, not as an argument that the recommendation is uncertain.

SELLER CHOICE RULE:
The seller chooses the final list price with Realtor advice. The report should show the trade-offs if the seller chooses outside the recommended range, but it should not undermine the selected range. If a seller chooses above the range, warn calmly about likely downsides such as fewer showings, longer Days in MLS, weaker early momentum, and increased buyer leverage. If a seller chooses below the range, explain the likely trade-off between traffic/speed and net proceeds.

{after_active_instruction}

TRUE BBC/TARZAN STANDARD RULE:
BBC does not mean “sounds smarter”; it means the report is smarter, clearer, and more useful. BBC is the seller-facing report at the front of the DOCX. It must not merely summarize data; it should explain the recommended position, the current market reality, the seller strategy, and what to watch next in plain English.

BBC VOICE AND FORMAT RULE:
BBC must stand alone as its own short report. Use the exact PART 1 heading and the numbered BBC section headings. Do not attach Tarzan support paragraphs under each BBC heading. BBC may refer the reader to Tarzan for backup detail, but it should remain readable as a seller-facing advisory report.

TARZAN RULE:
Tarzan must stand alone as its own analytical report after the page break. It should include valuation support, comp math, market momentum, price sensitivity, concessions, 1004MC/time review, market acceptance/repositioning, After-Active overlay when triggered, data verification, and methodology. Tarzan may be longer and more numeric, but it must still translate the math into practical meaning.


PRE-GPT REALTOR NOTES RULE:
Before writing the BBC/Tarzan report, review the supplied Realtor Notes, Buyer Considerations, Showing / Market Feedback Notes, MLS Listing History / Relist Notes, and Pre-GPT Realtor Notes Review inside STRUCTURED REPORT INPUT. These notes are not optional decoration; they are field judgment. If the subject is active, price-reduced, stale, previously expired/withdrawn under another ListingID, or has weak/no showing activity, the report must discuss that active-market evidence even when the selected report version is combined_bbc_tarzan. Do not let closed-comp math or current ListingID Days in MLS hide buyer-response evidence. If no Realtor Notes or Listing History notes were supplied, state this as a data limitation in Data Verification Notes and avoid pretending the report considered field feedback.

ACTIVE STATUS OVERRIDE RULE:
If STRUCTURED REPORT INPUT indicates the subject is Active, Coming Soon, Pending, Withdrawn, Expired, price-reduced, previously listed under another ListingID, relisted after expiration/withdrawal, or has showing/market feedback, include an After-Active Property Review. The key question becomes showing conversion, cumulative exposure, and next action, not only pre-list valuation support.

MLS LISTING HISTORY / RELIST RULE:
A current MLS export may only show the current ListingID and may make a relisted property look fresh. If listing-history notes are supplied, preserve and interpret them. Compare current ListingID Days in MLS against prior ListingID exposure, expired/withdrawn history, price reductions, and cumulative exposure. If listing-history notes are not supplied, state that prior ListingID history was not provided and cumulative exposure may be understated.

ADDITIONAL NOTES PROVIDED RULE:
If Realtor notes, buyer-consideration notes, property notes, upgrade notes, MLS listing-history/relist notes, market/showing feedback, or other note fields are supplied in report_input, they must appear visibly in the report under “Additional Notes Provided.” The report may interpret the notes, but it must also preserve them so the agent can confirm they were considered. If notes are unclear or unverified, place them in Data Verification Notes or state that they require field confirmation.

KNOWN UPGRADE RULE:
Known completed upgrades, remodeling, repairs, system replacements, and buyer-confidence improvements should support the selected range only when they are supplied as Realtor notes, verified source data, comp remarks, or other report_input evidence. Do not argue that the range could be higher “if upgraded” unless the selected range has actually changed or the upgrade is entered as known information.

CAVEAT RELEVANCE RULE:
Caveats must be material, report-specific, and decision-relevant. Include caveats only when they affect price position, buyer confidence, showing response, Days in MLS, negotiation leverage, concessions, inspection risk, current competition, or the subject’s comparison to selected comps. Do not include generic filler such as “clean the house” or “consider radon” unless supported by Realtor notes, buyer feedback, subject facts, market behavior, or meaningful comp differences.

AGENT REVIEW INPUTS RULE:
Agent Review Inputs are a required body section in every report immediately after the price range visual. Include:
- Upgrades / Condition: Ultra Low | Low | Medium Low | Medium | Medium High | High | Fully Remodeled
- Buyer Confidence / Risk Items: Roof; Sewer scope; Radon mitigation; HVAC age / serviceability; Smoke / odor concern; Water intrusion / basement moisture; Electrical / plumbing concerns; Structural concerns; Major deferred maintenance
These are circle-able agent review reminders, not automatic price reductions.

PRICING LOGIC STACK INTERPRETATION RULE:
The Recommended Price Logic stack is not a second valuation model. It is a plain-language black-and-white review checklist showing the selected range, working midpoint, comp adjustment status, market momentum review, DIM/acceptance review, 1004MC/time review, price sensitivity review, feature/buyer-perception review, and final recommended position. When an adjustment line says $0, explain that no separate dollar adjustment was applied because the data did not support one. If a serious caveat exists, discuss it in the appropriate Market Momentum, Market Acceptance, Price Sensitivity, or After-Active section.

PRICE / MARKET BEHAVIOR RULES:
- The value range is based on closed comparable evidence and known property information.
- Current competition affects buyer choice, launch posture, showing response, and negotiation leverage.
- Momentum measures speed/activity.
- Price Sensitivity & Seller Net Behavior measures how often sellers had to reduce, concede, or net below original list before buyers accepted the property.
- Use Closed-only MOI as the primary seller-facing MOI: Active listings divided by latest 90-day average monthly Closed sales.
- Treat pending-inclusive MOI as a secondary demand-pressure indicator only.
- Use the latest 90-day closed window available in the uploaded file for absorption, and label it that way when the file does not run through the current date.

MARKET ACCEPTANCE / REPOSITIONING RULE:
This section is not an automatic price cut. It asks whether the market is accepting the current price, condition, presentation, and terms. A timely, data-supported repositioning can preserve freshness; a late reactive reduction after long market time can signal weakness and increase buyer leverage. Explain this carefully and only when supported by the facts.

BACKEND LANGUAGE BAN:
Never use seller-facing backend words such as engine, payload, module, API, deterministic engine, debug, prompt, schema, JSON, GPT, net_price, close_price, concessions_amount, or time_adjustment. Use seller-facing language such as “the analysis,” “market review,” “net price after reported concessions,” and “market-pattern inputs.”

STYLE RULES:
- Use “Days in MLS,” not DOM.
- Avoid confidence scores.
- Avoid verbose caveats.
- Do not end with “If you want...” language.
- Do not use the word “reconciliation” in the seller-facing report. Use “Pricing Basis” or “How the Value Was Determined.”
- Include distance only if supplied. Do not invent distance.
- Format comparable evidence as a markdown table with: Address, Closed / Net Price, Close Date, Days in MLS, Total Adjusted Price.

ICHIBAN GOVERNANCE:
{json.dumps(governance, indent=2, ensure_ascii=False, default=str)}

STRUCTURED REPORT INPUT:
{json.dumps(report_input, indent=2, ensure_ascii=False, default=str)}

Now write the final ICHIBAN INSIGHT report in the locked order for the requested mode. Do not include a closing offer, assistant note, or any “If you want...” language.
""".strip()
