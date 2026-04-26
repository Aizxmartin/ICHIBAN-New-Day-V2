from __future__ import annotations

from typing import Any, Dict

from core.comp_engine import run_comp_engine


def run_valuation(market_df, subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run valuation against an already-loaded, already-normalized dataframe.
    """
    if market_df is None:
        return {
            "error": "No normalized market dataframe was provided.",
        }

    results = run_comp_engine(market_df, subject_profile)
    return results