from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from core.comp_engine import run_comp_engine


def run_valuation(
    market_df: pd.DataFrame,
    subject_profile: Dict[str, Any],
    one_hundred_four_mc_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run the valuation engine against the normalized MLS dataframe.

    Module 3 owns upload/header detection, normalization, and optional 1004MC
    time-trend intake. Module 4 passes structured data here so the valuation
    layer does not re-read uploads or retain raw report files.
    """
    if market_df is None:
        return {"error": "No normalized market dataframe was provided."}

    results = run_comp_engine(market_df, subject_profile or {})

    # Keep the controller return type easy for Streamlit/reporting code to use.
    if hasattr(results, "__dataclass_fields__"):
        from dataclasses import asdict

        output = asdict(results)
    else:
        output = dict(results)

    # 1004MC is collected before valuation so future time-adjustment logic can use
    # the stored annual/monthly trend. For now it is carried forward without
    # forcing the valuation to fail when absent.
    output["one_hundred_four_mc_summary"] = one_hundred_four_mc_summary or {
        "is_supplied": False,
        "source_status": "not_supplied",
    }
    return output
