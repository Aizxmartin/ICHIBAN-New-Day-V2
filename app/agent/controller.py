import pandas as pd

from core.market_mapping import inspect_market_file


def run_valuation(market_file, subject_profile):
    inspection = inspect_market_file(market_file)
    df = inspection.dataframe

    closed_mask = df["mls_status"].astype(str).str.lower().isin(["closed", "sold"]) if "mls_status" in df.columns else pd.Series([False] * len(df), index=df.index)
    closed_df = df.loc[closed_mask].copy()

    subject_ag = subject_profile.get("above_grade_sqft")
    filtered_closed = closed_df
    if subject_ag and "above_grade_sqft" in closed_df.columns:
        lower = float(subject_ag) * 0.85
        upper = float(subject_ag) * 1.10
        filtered_closed = closed_df[(closed_df["above_grade_sqft"] >= lower) & (closed_df["above_grade_sqft"] <= upper)].copy()

    return {
        "rows_loaded": int(len(df)),
        "normalized_columns": list(df.columns),
        "detected_header_row": inspection.detected_header_row,
        "header_score": inspection.header_score,
        "matched_market_fields": inspection.matched_fields,
        "missing_preferred_market_fields": inspection.missing_preferred_fields,
        "closed_rows": int(len(closed_df)),
        "closed_rows_in_subject_size_band": int(len(filtered_closed)),
        "subject_summary": {
            "subject_address": subject_profile.get("subject_address"),
            "above_grade_sqft": subject_profile.get("above_grade_sqft"),
            "property_type": subject_profile.get("property_type"),
            "property_subtype": subject_profile.get("property_subtype"),
            "beds": subject_profile.get("beds"),
            "baths": subject_profile.get("baths"),
            "year_built": subject_profile.get("year_built"),
            "real_avm": subject_profile.get("real_avm"),
        },
    }
