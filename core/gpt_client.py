"""
OpenAI client for ICHIBAN final report generation.

This file is intentionally narrow:
- It loads the governance rules.
- It builds the report-writing prompt.
- It sends the completed analysis payload to the configured mini model.
- It returns the final narrative report text.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Union

from core.governance.load_governance import load_report_governance


DEFAULT_MODEL = os.getenv("ICHIBAN_OPENAI_MODEL", "gpt-5-mini")
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("ICHIBAN_MAX_OUTPUT_TOKENS", "8000"))


def generate_gpt_prompt(
    report_payload: Dict[str, Any],
    governance: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the prompt mini GPT receives.

    Mini GPT should explain the completed structured analysis, not invent or
    override valuation math.
    """
    governance = governance or load_report_governance()

    return f"""
You are the final report writer for ICHIBAN Insight.

Your job is to produce a deep, impressive, agent-grade real estate valuation and market strategy report.

Critical operating rules:
1. Do not recalculate or change deterministic math supplied by the local program.
2. Do not invent missing comparable data, missing adjustments, or market statistics.
3. Explain what the program did, what affected value, and how the evidence affects the go-to-market strategy.
4. Use the fixed report sections required by the governance JSON.
5. Write in deep-dive mode. Do not shorten the report merely to save space.
6. Avoid generic market commentary. Connect the local radius/micro-market to the specific subject property.
7. Address whether this property is likely to sell faster, slower, or in line with its micro-market, and why.
8. Include risk factors, buyer resistance, pricing sensitivity, and a recommended list price range when supported by the supplied payload.
9. Include the required ICHIBAN methodology/disclaimer language near the end.
10. Present the output as clean report text suitable for .docx export.

ICHIBAN GOVERNANCE JSON:
{json.dumps(governance, indent=2, ensure_ascii=False, default=str)}

COMPLETED ICHIBAN ANALYSIS PAYLOAD:
{json.dumps(report_payload, indent=2, ensure_ascii=False, default=str)}

Now write the final ICHIBAN Insight report.
""".strip()


def _extract_response_text(response: Any) -> str:
    """Extract text from the OpenAI Responses API object."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    # Fallback for SDK variations.
    try:
        chunks = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks)
    except Exception:
        pass

    return str(response)


def run_gpt_report(
    prompt_or_payload: Union[str, Dict[str, Any]],
    governance: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> str:
    """
    Generate the final ICHIBAN report using the configured OpenAI model.

    Backward-compatible behavior:
    - If prompt_or_payload is a string, it is sent as the prompt.
    - If prompt_or_payload is a dict, governance is loaded and a complete prompt is built.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. For local use, set it before running Streamlit. "
            "Example in Windows CMD: setx OPENAI_API_KEY \"your_api_key_here\""
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python package is not installed. Run: python -m pip install openai"
        ) from exc

    if isinstance(prompt_or_payload, str):
        prompt = prompt_or_payload
    else:
        prompt = generate_gpt_prompt(prompt_or_payload, governance=governance)

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model or DEFAULT_MODEL,
        input=prompt,
        max_output_tokens=max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
    )

    return _extract_response_text(response)
