from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re

import pandas as pd


ENGINE_VERSION = "valuation_engine_v2c_market_acceptance_price_sensitivity"


ADJUSTMENT_RATES = {
    "above_grade_sqft": 40,
    "finished_basement_sqft": 20,
    "unfinished_basement_sqft": 5,
}


COLUMN_ALIASES = {
    "status": [
        "status",
        "mlsstatus",
        "mls status",
        "standardstatus",
        "standard status",
        "property status",
    ],
    "close_price": [
        "closeprice",
        "close price",
        "closedprice",
        "closed price",
        "soldprice",
        "sold price",
        "saleprice",
        "sale price",
    ],
    "list_price": [
        "listprice",
        "list price",
        "currentprice",
        "current price",
        "originallistprice",
        "original list price",
    ],
    "original_list_price": [
        "originallistprice",
        "original list price",
        "originalprice",
        "original price",
    ],
    "previous_list_price": [
        "previouslistprice",
        "previous list price",
        "previousprice",
        "previous price",
    ],
    "concessions": [
        "Concessions Amount",
        "concessionsamount",
        "concessions amount",
        "sellerconcessionsamount",
        "seller concessions amount",
        "seller concession amount",
        "seller concession",
        "sellerconcessions",
        "seller concessions",
        "sellerpaidclosingcosts",
        "seller paid closing costs",
        "closingcosts",
        "closing costs",
        "concessions",
    ],

    # MLS square-footage safety rule:
    # Above Grade Finished Area is the only MLS field allowed to drive primary comp sizing.
    # Do not substitute Living Area, Building Area Total, or generic SqFt for this field.
    "above_grade_sqft": [
        "Above Grade Finished Area",
        "abovegradefinishedarea",
        "above grade finished area",
        "abovegradefinishedsqft",
        "above grade finished sqft",
        "above grade finished sf",
    ],
    "building_area_total": [
        "Building Area Total",
        "buildingareatotal",
        "building area total",
    ],
    "living_area": [
        "Living Area",
        "livingarea",
        "living area",
    ],

    "basement_sqft": [
        "belowgradearea",
        "below grade area",
        "belowgradesqft",
        "below grade sqft",
        "basementsqft",
        "basement sqft",
        "basement sf",
        "totalbasementsqft",
        "total basement sqft",
        "bldg sq ft basement",
    ],
    "finished_basement_sqft": [
        "Below Grade Finished Area",
        "belowgradefinishedarea",
        "below grade finished area",
        "belowgradefinishedsqft",
        "below grade finished sqft",
        "finishedbasementsqft",
        "finished basement sqft",
        "finished basement sf",
        "bldg sq ft finished basement",
    ],
    "unfinished_basement_sqft": [
        "Below Grade Unfinished Area",
        "belowgradeunfinishedarea",
        "below grade unfinished area",
        "belowgradeunfinishedsqft",
        "below grade unfinished sqft",
        "unfinishedbasementsqft",
        "unfinished basement sqft",
        "unfinished basement sf",
    ],
    "basement_description": [
        "Basement",
        "basement",
        "basement description",
        "basementdescription",
        "basement details",
        "basementdetails",
    ],
    "year_built": [
        "yearbuilt",
        "year built",
    ],
    "beds": [
        "beds",
        "bedrooms",
        "bedroomstotal",
        "bedrooms total",
    ],
    "baths": [
        "baths",
        "bathrooms",
        "bathroomstotal",
        "bathrooms total",
        "totalbaths",
        "total baths",
    ],
    "days_in_mls": [
        "daysinmls",
        "days in mls",
        "dim",
        "dom",
        "daysonmarket",
        "days on market",
        "cumulativedaysonmarket",
        "cumulative days on market",
    ],
    "close_date": [
        "closedate",
        "close date",
        "sold date",
        "solddate",
        "closingdate",
        "closing date",
    ],
    "address": [
        "address",
        "fulladdress",
        "full address",
        "unparsedaddress",
        "unparsed address",
        "propertyaddress",
        "property address",
        "streetaddress",
        "street address",
    ],
    "street_number": [
        "streetnumbernumeric",
        "street number numeric",
        "streetnumber",
        "street number",
    ],
    "street_name": [
        "streetname",
        "street name",
    ],
    "city": [
        "city",
    ],
    "subdivision": [
        "subdivision",
        "subdivisionname",
        "subdivision name",
    ],
    "association_name": [
        "associationname",
        "association name",
        "association",
        "hoa name",
        "hoa",
    ],
    "association_name_2": [
        "associationname2",
        "association name 2",
        "association2name",
        "association 2 name",
        "hoa name 2",
        "hoa2",
    ],
    "association_fee_total_annual": [
        "associationfeetotalannual",
        "association fee total annual",
        "associationfeeannual",
        "association fee annual",
        "hoa annual fee",
        "hoa fee annual",
    ],
    "property_subtype": [
        "propertysubtype",
        "property sub type",
        "property subtype",
        "propertytype",
        "property type",
        "structuretype",
        "structure type",
    ],
    "levels": [
        "Levels",
        "levels",
        "stories",
        "story",
        "architecturalstyle",
        "architectural style",
        "style",
    ],
    "public_remarks": [
        "publicremarks",
        "public remarks",
        "remarks",
        "marketing remarks",
    ],
    "broker_remarks": [
        "brokerremarks",
        "broker remarks",
        "private remarks",
        "private remarks - broker",
    ],
}


def run_valuation_engine(
    subject_profile: Dict[str, Any],
    market_data: Any,
    one_hundred_four_mc_summary: Optional[Dict[str, Any]] = None,
    competition_market_data: Any = None,
    report_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ICHIBAN INSIGHT Valuation Engine v2B.

    Purpose:
    - Build selected comparable evidence from the uploaded MLS comp file.
    - Apply deterministic adjustments.
    - Produce the Selected Comparable Evidence Range.
    - Produce the Online Estimated Value range from Zillow, Redfin, and RealAVM.
    - Produce a limited Market Momentum section only when active/pending/sold data is present.
    - Leave final seller-facing pricing posture and Market Entry Range to the GPT layer.

    Key safety rule:
    - Subject above-grade square footage must not be populated from Realist total-finished fields.
      The engine first uses direct above-ground / above-grade fields, then may infer above-grade
      from total finished minus finished basement, with a verification note.
    """

    one_hundred_four_mc_summary = one_hundred_four_mc_summary or {}
    report_type = "Tarzan Valuation Analysis"

    market_workflow_rule = {
        "workflow_name": "1004MC / Competition Market File Rule",
        "recommended_search": {
            "lookback": "12-month lookback",
            "property_type": "Single Family Residence when subject is Single Family",
            "radius": "Approximately 3-mile radius, expandable to 3–5 miles if needed",
            "price_band": "Approximately $100K below to $100K above projected range",
            "square_footage": "Use established above-grade / main-upper-level SF range parameters",
            "statuses": "Include Active, Pending, Closed, and optionally Expired/Withdrawn",
            "levels": "Levels may include all levels for competition/momentum, but level differences must be tagged",
        },
        "file_roles": {
            "valuation_comp_file": "Adjusted comps, Ruler Range, and recommended value range",
            "competition_market_file": "Market pattern, absorption, current competition, projected MOI range, seller caveats, and momentum discussion",
        },
        "report_language_rule": (
            "The value range is based on closed comparable evidence. The market momentum section reviews a broader "
            "competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction."
        ),
    }

    warnings: List[str] = []
    notes: List[str] = []
    data_verification_notes: List[str] = []

    df = _as_dataframe(market_data)

    if df.empty:
        return {
            "engine_version": ENGINE_VERSION,
            "engine_status": "blocked",
            "reason": "Market data is empty or could not be converted to a DataFrame.",
            "warnings": warnings,
        }

    subject = _build_subject_features(
        subject_profile=subject_profile,
        warnings=warnings,
        data_verification_notes=data_verification_notes,
    )

    column_map = _detect_columns(df)

    prepared = _prepare_market_dataframe(
        df=df,
        column_map=column_map,
        subject=subject,
        warnings=warnings,
        notes=notes,
    )

    all_prepared_df = prepared["all_prepared_df"]
    closed_df = prepared["closed_df"]
    comp_candidates_df = prepared["comp_candidates_df"]
    subject_market_snapshot = _detect_subject_market_snapshot(subject, all_prepared_df)

    if comp_candidates_df.empty:
        return {
            "engine_version": ENGINE_VERSION,
            "engine_status": "blocked",
            "reason": "No usable closed comparable sales were available after preparation.",
            "subject_summary": subject,
            "column_map": column_map,
            "subject_market_snapshot": subject_market_snapshot,
            "market_rows_loaded": int(len(df)),
            "closed_rows_available": int(len(closed_df)),
            "warnings": warnings,
            "notes": notes,
            "data_verification_notes": data_verification_notes,
        }

    adjusted_df = _apply_adjustments_and_scoring(
        comp_df=comp_candidates_df,
        subject=subject,
        one_hundred_four_mc_summary=one_hundred_four_mc_summary,
        warnings=warnings,
        notes=notes,
    )

    selected_df = _select_best_comps(adjusted_df, notes)

    online_estimated_value = _calculate_online_estimated_value(subject_profile)

    selected_comparable_evidence_range = _calculate_selected_comparable_evidence_range(
        selected_df=selected_df,
        warnings=warnings,
        notes=notes,
    )

    comp_statistics = _calculate_comp_statistics(selected_df)

    competition_rows_loaded = 0
    competition_market_supplied = competition_market_data is not None

    if competition_market_supplied:
        competition_df = _as_dataframe(competition_market_data)
        competition_rows_loaded = int(len(competition_df)) if competition_df is not None else 0
    else:
        competition_df = pd.DataFrame()

    if competition_market_supplied and not competition_df.empty:
        competition_column_map = _detect_columns(competition_df)
        competition_notes: List[str] = []
        competition_warnings: List[str] = []
        competition_prepared = _prepare_market_dataframe(
            df=competition_df,
            column_map=competition_column_map,
            subject=subject,
            warnings=competition_warnings,
            notes=competition_notes,
        )
        market_momentum = _calculate_limited_market_momentum(
            all_prepared_df=competition_prepared["all_prepared_df"],
            column_map=competition_column_map,
            notes=notes,
        )
        market_momentum.update(
            {
                "status": "broader_competition_file_supplied",
                "source": "1004MC / Competition Market File",
                "competition_market_rows_loaded": competition_rows_loaded,
                "valuation_boundary": market_workflow_rule["report_language_rule"],
                "recommended_search_rule": market_workflow_rule["recommended_search"],
                "important_limitation": (
                    "The 1004MC / Competition Market File supports market pattern, absorption, current competition, projected MOI range, "
                    "seller caveats, and momentum discussion. It does not replace the Valuation Comp File for adjusted closed-comp value support."
                ),
            }
        )
        price_sensitivity_and_seller_net_behavior = _calculate_price_sensitivity_and_seller_net_behavior(
            all_prepared_df=competition_prepared["all_prepared_df"],
            source_label="1004MC / Competition Market File",
        )
        market_momentum["price_sensitivity_summary"] = price_sensitivity_and_seller_net_behavior.get("summary_for_momentum")
        if competition_notes:
            notes.extend([f"Competition market file: {note}" for note in competition_notes])
    else:
        market_momentum = _calculate_limited_market_momentum(
            all_prepared_df=all_prepared_df,
            column_map=column_map,
            notes=notes,
        )
        market_momentum.update(
            {
                "valuation_boundary": market_workflow_rule["report_language_rule"],
                "recommended_competition_file": market_workflow_rule["recommended_search"],
            }
        )
        price_sensitivity_and_seller_net_behavior = _calculate_price_sensitivity_and_seller_net_behavior(
            all_prepared_df=all_prepared_df,
            source_label="Valuation Comp File fallback",
        )
        market_momentum["price_sensitivity_summary"] = price_sensitivity_and_seller_net_behavior.get("summary_for_momentum")

    result = {
        "engine_version": ENGINE_VERSION,
        "engine_status": "success",
        "engine_scope": "pre_api_selected_comparable_evidence",
        "report_type": report_type,
        "market_workflow_rule": market_workflow_rule,
        "market_file_roles": market_workflow_rule["file_roles"],
        "important_boundary_note": (
            "This pre-API engine selects and adjusts comparable evidence. "
            "It does not create the final GPT-qualified Market Entry Range. "
            "The GPT layer should review comp quality, remarks, condition, live competition, "
            "market momentum, and adjustment reasonableness before writing seller-facing conclusions."
        ),
        "subject_summary": subject,
        "adjustment_rates": ADJUSTMENT_RATES,
        "market_rows_loaded": int(len(df)),
        "valuation_comp_rows_loaded": int(len(df)),
        "competition_market_rows_loaded": competition_rows_loaded,
        "closed_rows_available": int(len(closed_df)),
        "comp_rows_scored": int(len(adjusted_df)),
        "comp_rows_selected": int(len(selected_df)),
        "column_map": column_map,
        "subject_market_snapshot": subject_market_snapshot,
        "online_estimated_value": online_estimated_value,
        "selected_comparable_evidence_range": selected_comparable_evidence_range,
        "comp_statistics": comp_statistics,
        "market_momentum_and_buyer_competition": market_momentum,
        "price_sensitivity_and_seller_net_behavior": price_sensitivity_and_seller_net_behavior,
        "market_conditions_1004mc": _summarize_1004mc(one_hundred_four_mc_summary),
        "selected_adjusted_comps": _build_adjusted_comp_records(selected_df),
        "all_scored_comps_preview": _build_adjusted_comp_records(adjusted_df.head(15)),
        "gpt_review_package": {
            "requires_gpt_qualification": True,
            "gpt_should_review": [
                "whether selected comps are true comps or only support comps",
                "whether superior comps should support only the upper end",
                "whether inferior comps should support the lower end",
                "public remarks and broker remarks for condition, updating, layout, location, and buyer appeal",
                "whether the Online Estimated Value is aligned with the selected comparable evidence",
                "whether market momentum supports Protective, Competitive, Evidence-Aligned, Strategic Upper, or Aspirational Entry",
                "whether the seller-facing Market Entry Range should be narrowed, qualified, or posture-labeled",
                "whether active and pending same-micro-market properties should be treated as market signals rather than closed comps",
                "whether HOA, gated-pocket, subdivision, or association differences affect buyer perception",
            ],
            "final_gpt_output_expected_later": [
                "Pricing Posture",
                "Comparable-Supported Market Entry Range",
                "seller-facing explanation",
            ],
        },
        "data_verification_notes": data_verification_notes,
        "warnings": warnings,
        "notes": notes,
    }

    return _json_safe(result)


# ---------------------------------------------------------------------
# Subject handling
# ---------------------------------------------------------------------

def _build_subject_features(
    subject_profile: Dict[str, Any],
    warnings: List[str],
    data_verification_notes: List[str],
) -> Dict[str, Any]:
    """
    Build a normalized subject profile from Realist/manual/other intake.

    This function intentionally treats Realist/county data as useful but imperfect.
    It avoids using broad Realist total-finished fields as above-grade square footage.
    """

    # 1. Exact/direct above-grade fields only.
    direct_above_grade = _first_number(
        subject_profile,
        [
            "above_grade_sqft",
            "Above Grade Finished Area",
            "Bldg Sq Ft - Above Ground",
            "bldg_sq_ft_above_ground",
        ],
    )

    # 2. Realist total-finished fields. These are NOT above grade.
    total_finished_sqft = _first_number(
        subject_profile,
        [
            "total_finished_sqft",
            "Bldg Sq Ft - Finished",
            "bldg_sq_ft_finished",
            "Bldg Sq Ft",
            "building_sqft",
            "realist_summary_finished_sqft",
        ],
    )

    basement_total = _first_number(
        subject_profile,
        [
            "basement_sqft",
            "total_basement_sqft",
            "below_grade_sqft",
            "below_grade_area",
            "Bldg Sq Ft - Basement",
            "bldg_sq_ft_basement",
        ],
    )

    finished_basement = _first_number(
        subject_profile,
        [
            "finished_basement_sqft",
            "below_grade_finished_sqft",
            "below_grade_finished_area",
            "Bldg Sq Ft - Finished Basement",
            "bldg_sq_ft_finished_basement",
        ],
    )

    unfinished_basement = _first_number(
        subject_profile,
        [
            "unfinished_basement_sqft",
            "below_grade_unfinished_sqft",
            "below_grade_unfinished_area",
            "Bldg Sq Ft - Unfinished Basement",
            "bldg_sq_ft_unfinished_basement",
        ],
    )

    building_area_total = _first_number(
        subject_profile,
        [
            "building_area_total",
            "Building Area Total",
            "Bldg Sq Ft - Total",
            "bldg_sq_ft_total",
            "total_building_area",
            "total_sqft",
        ],
    )

    living_area = _first_number(
        subject_profile,
        [
            "living_area",
            "Living Area",
            "MLS Sq Ft",
            "total_finished_living_area",
        ],
    )

    # 3. Basement derivation and verification-tolerant fallback.
    if basement_total is not None and finished_basement is not None and unfinished_basement is None:
        unfinished_basement = max(basement_total - finished_basement, 0)

    if basement_total is None and finished_basement is not None:
        basement_total = finished_basement
        unfinished_basement = 0
        data_verification_notes.append(
            "Subject total basement square footage was missing; using finished basement square footage as total basement until verified."
        )

    if basement_total is not None and finished_basement is None:
        finished_basement = 0
        unfinished_basement = basement_total
        data_verification_notes.append(
            "Subject finished basement square footage was missing; treating basement as unfinished until verified."
        )

    # 4. Above-grade selection / correction.
    above_grade = direct_above_grade
    above_grade_source = "direct_above_grade_field" if direct_above_grade is not None else None

    if above_grade is None and total_finished_sqft is not None and finished_basement is not None:
        inferred = total_finished_sqft - finished_basement
        if inferred > 0:
            above_grade = inferred
            above_grade_source = "inferred_from_total_finished_minus_finished_basement"
            data_verification_notes.append(
                f"Above-grade square footage was inferred because the direct above-grade field was missing. "
                f"Calculation used Total Finished SqFt ({round(total_finished_sqft)}) minus Finished Basement SqFt "
                f"({round(finished_basement)}) = {round(inferred)}. Manual verification recommended."
            )

    if (
        direct_above_grade is not None
        and total_finished_sqft is not None
        and finished_basement is not None
        and round(direct_above_grade + finished_basement) == round(total_finished_sqft)
    ):
        data_verification_notes.append(
            f"Square footage cross-check passed: Above Ground SqFt ({round(direct_above_grade)}) "
            f"+ Finished Basement SqFt ({round(finished_basement)}) = Total Finished SqFt ({round(total_finished_sqft)})."
        )

    if (
        above_grade is not None
        and total_finished_sqft is not None
        and finished_basement is not None
        and round(above_grade) == round(total_finished_sqft)
        and finished_basement > 0
    ):
        corrected = total_finished_sqft - finished_basement
        if corrected > 0:
            data_verification_notes.append(
                f"Above-grade square footage appeared to equal Total Finished SqFt ({round(total_finished_sqft)}). "
                f"Corrected above-grade to {round(corrected)} by subtracting Finished Basement SqFt ({round(finished_basement)})."
            )
            above_grade = corrected
            above_grade_source = "corrected_from_total_finished_minus_finished_basement"

    if above_grade is None:
        warnings.append(
            "Subject Above Grade Finished Area is missing. Comp selection quality will be reduced."
        )

    return {
        "subject_address": subject_profile.get("subject_address")
        or subject_profile.get("address")
        or subject_profile.get("situs_address"),
        "above_grade_sqft": _round_number(above_grade),
        "above_grade_source": above_grade_source,
        "basement_sqft": _round_number(basement_total),
        "finished_basement_sqft": _round_number(finished_basement),
        "unfinished_basement_sqft": _round_number(unfinished_basement),
        "total_finished_sqft": _round_number(total_finished_sqft),
        "living_area": _round_number(living_area),
        "building_area_total": _round_number(building_area_total),
        "property_type": subject_profile.get("property_type"),
        "property_subtype": subject_profile.get("property_subtype")
        or subject_profile.get("property_sub_type")
        or subject_profile.get("land_use_county"),
        "levels": subject_profile.get("levels")
        or subject_profile.get("Levels")
        or subject_profile.get("style")
        or subject_profile.get("Style")
        or subject_profile.get("stories")
        or subject_profile.get("Stories")
        or subject_profile.get("architectural_style")
        or subject_profile.get("Architectural Style"),
        "subject_layout_notes": subject_profile.get("subject_layout_notes")
        or subject_profile.get("layout_notes")
        or subject_profile.get("style_notes"),
        "beds": _first_number(subject_profile, ["beds", "bedrooms"]),
        "baths": _first_number(subject_profile, ["baths", "bathrooms"]),
        "year_built": _first_number(subject_profile, ["year_built", "Year Built"]),
        "lot_sqft": _first_number(subject_profile, ["lot_sqft", "lot_size_sqft", "land_sqft", "land_square_feet"]),
        "neighborhood_name": subject_profile.get("neighborhood_name")
        or subject_profile.get("neighborhood"),
        "subdivision": subject_profile.get("subdivision"),
        "zoning": subject_profile.get("zoning"),
        "real_avm": _first_number(subject_profile, ["real_avm", "RealAVM"]),
        "real_avm_range_low": _first_number(subject_profile, ["real_avm_range_low"]),
        "real_avm_range_high": _first_number(subject_profile, ["real_avm_range_high"]),
        "zillow_estimate": _first_number(subject_profile, ["zillow_estimate", "zestimate"]),
        "redfin_estimate": _first_number(subject_profile, ["redfin_estimate"]),
    }


# ---------------------------------------------------------------------
# Market data preparation
# ---------------------------------------------------------------------

def _as_dataframe(market_data: Any) -> pd.DataFrame:
    if market_data is None:
        return pd.DataFrame()

    if isinstance(market_data, pd.DataFrame):
        return market_data.copy()

    if isinstance(market_data, list):
        return pd.DataFrame(market_data)

    if isinstance(market_data, dict):
        try:
            return pd.DataFrame(market_data)
        except Exception:
            return pd.DataFrame([market_data])

    return pd.DataFrame()


def _detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    detected: Dict[str, Optional[str]] = {}

    normalized_columns = {
        _normalize_column_name(column): column
        for column in df.columns
    }

    for logical_name, aliases in COLUMN_ALIASES.items():
        found = None

        for alias in aliases:
            normalized_alias = _normalize_column_name(alias)

            if normalized_alias in normalized_columns:
                found = normalized_columns[normalized_alias]
                break

        if found is None:
            for normalized_column, original_column in normalized_columns.items():
                if any(_normalize_column_name(alias) in normalized_column for alias in aliases):
                    found = original_column
                    break

        detected[logical_name] = found

    return detected


def _remarks_suggest_finished_basement(text: Any) -> bool:
    raw = str(text or "").lower()
    if not raw:
        return False

    has_basement_signal = "basement" in raw or "walkout" in raw or "walk-out" in raw
    has_finished_signal = re.search(r"(?<!un)finished", raw) is not None or "partially finish" in raw
    has_only_unfinished_signal = "unfinished basement" in raw and not has_finished_signal

    return bool(has_basement_signal and has_finished_signal and not has_only_unfinished_signal)


def _infer_finished_basement_from_living_area_and_remarks(row: pd.Series) -> Tuple[Optional[float], bool]:
    direct_finished = _to_number(row.get("_finished_basement_sqft"))
    if direct_finished is not None and direct_finished > 0:
        return direct_finished, False

    living_area = _to_number(row.get("_living_area"))
    above_grade = _to_number(row.get("_above_grade_sqft"))

    if living_area is None or above_grade is None:
        return direct_finished, False

    inferred = living_area - above_grade
    if inferred <= 100:
        return direct_finished, False

    remarks_text = " ".join(
        str(row.get(key) or "")
        for key in ["_basement_description", "_public_remarks", "_broker_remarks"]
    )

    if not _remarks_suggest_finished_basement(remarks_text):
        return direct_finished, False

    # Keep inference inside normal basement-size guardrails to avoid total-area mistakes.
    if inferred > 4000:
        return direct_finished, False

    return inferred, True


def _derive_total_basement_after_finished_inference(
    basement_total: Any,
    finished_basement: Any,
    unfinished_basement: Any,
) -> Optional[float]:
    basement_total_num = _to_number(basement_total)
    finished_num = _to_number(finished_basement)
    unfinished_num = _to_number(unfinished_basement)

    if basement_total_num is not None:
        if finished_num is not None and finished_num > basement_total_num and unfinished_num:
            return finished_num + unfinished_num
        return basement_total_num

    if finished_num is not None and unfinished_num is not None:
        return finished_num + unfinished_num

    if finished_num is not None:
        return finished_num

    return None


def _prepare_market_dataframe(
    df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
    subject: Dict[str, Any],
    warnings: List[str],
    notes: List[str],
) -> Dict[str, Any]:
    working = df.copy()

    close_col = column_map.get("close_price")
    list_col = column_map.get("list_price")
    original_list_col = column_map.get("original_list_price")
    previous_list_col = column_map.get("previous_list_price")
    concessions_col = column_map.get("concessions")
    ag_col = column_map.get("above_grade_sqft")
    living_area_col = column_map.get("living_area")
    building_area_total_col = column_map.get("building_area_total")
    basement_col = column_map.get("basement_sqft")
    finished_basement_col = column_map.get("finished_basement_sqft")
    unfinished_basement_col = column_map.get("unfinished_basement_sqft")
    basement_description_col = column_map.get("basement_description")
    status_col = column_map.get("status")
    year_col = column_map.get("year_built")
    close_date_col = column_map.get("close_date")
    days_col = column_map.get("days_in_mls")
    subtype_col = column_map.get("property_subtype")
    levels_col = column_map.get("levels")
    subdivision_col = column_map.get("subdivision")
    association_name_col = column_map.get("association_name")
    association_name_2_col = column_map.get("association_name_2")
    association_fee_col = column_map.get("association_fee_total_annual")
    public_remarks_col = column_map.get("public_remarks")
    broker_remarks_col = column_map.get("broker_remarks")

    if close_col is None:
        warnings.append("Close Price column was not detected. Closed comparable valuation may be blocked.")

    if close_col:
        working["_close_price"] = working[close_col].apply(_to_number)
    else:
        working["_close_price"] = None

    if list_col:
        working["_list_price"] = working[list_col].apply(_to_number)
    else:
        working["_list_price"] = None

    if original_list_col:
        working["_original_list_price"] = working[original_list_col].apply(_to_number)
    else:
        working["_original_list_price"] = working["_list_price"]

    if previous_list_col:
        working["_previous_list_price"] = working[previous_list_col].apply(_to_number)
    else:
        working["_previous_list_price"] = None

    if concessions_col:
        working["_concessions"] = working[concessions_col].apply(_to_number).fillna(0)
    else:
        working["_concessions"] = 0
        notes.append("No concessions column detected; net price equals close price for closed comps.")

    if ag_col:
        working["_above_grade_sqft"] = working[ag_col].apply(_to_number)
    else:
        working["_above_grade_sqft"] = None
        warnings.append(
            "Above Grade Finished Area column was not detected. "
            "Comp filtering cannot safely use Living Area or Building Area Total as a substitute."
        )

    if living_area_col:
        working["_living_area"] = working[living_area_col].apply(_to_number)
    else:
        working["_living_area"] = None

    if building_area_total_col:
        working["_building_area_total"] = working[building_area_total_col].apply(_to_number)
    else:
        working["_building_area_total"] = None

    if basement_col:
        working["_basement_sqft"] = working[basement_col].apply(_to_number)
    else:
        working["_basement_sqft"] = None
        notes.append("No total basement square footage column detected.")

    if finished_basement_col:
        working["_finished_basement_sqft"] = working[finished_basement_col].apply(_to_number)
    else:
        working["_finished_basement_sqft"] = None
        notes.append("No finished basement square footage column detected.")

    if unfinished_basement_col:
        working["_unfinished_basement_sqft"] = working[unfinished_basement_col].apply(_to_number)
    else:
        working["_unfinished_basement_sqft"] = None

    if basement_description_col:
        working["_basement_description"] = working[basement_description_col].astype(str)
    else:
        working["_basement_description"] = ""

    if public_remarks_col:
        working["_public_remarks"] = working[public_remarks_col].astype(str)
    else:
        working["_public_remarks"] = ""

    if broker_remarks_col:
        working["_broker_remarks"] = working[broker_remarks_col].astype(str)
    else:
        working["_broker_remarks"] = ""

    working["_finished_basement_inferred"] = False
    inferred_finished_values = []
    inferred_flags = []
    for _idx, row in working.iterrows():
        inferred_value, inferred_flag = _infer_finished_basement_from_living_area_and_remarks(row)
        inferred_finished_values.append(inferred_value)
        inferred_flags.append(inferred_flag)
    working["_finished_basement_sqft"] = inferred_finished_values
    working["_finished_basement_inferred"] = inferred_flags

    inferred_count = int(sum(1 for flag in inferred_flags if flag))
    if inferred_count:
        notes.append(
            f"Inferred finished basement square footage for {inferred_count} row(s) where Below Grade Finished Area was blank/zero but Living Area exceeded Above Grade Finished Area and remarks indicated a finished basement. Agent verification required."
        )

    working["_basement_sqft"] = working.apply(
        lambda row: _derive_total_basement_after_finished_inference(
            row.get("_basement_sqft"),
            row.get("_finished_basement_sqft"),
            row.get("_unfinished_basement_sqft"),
        ),
        axis=1,
    )

    working["_unfinished_basement_sqft"] = working.apply(
        lambda row: _derive_unfinished_basement(
            row.get("_basement_sqft"),
            row.get("_finished_basement_sqft"),
            row.get("_unfinished_basement_sqft"),
        ),
        axis=1,
    )

    if year_col:
        working["_year_built"] = working[year_col].apply(_to_number)
    else:
        working["_year_built"] = None

    if close_date_col:
        working["_close_date"] = working[close_date_col].apply(_to_datetime)
    else:
        working["_close_date"] = None

    if days_col:
        working["_days_in_mls"] = working[days_col].apply(_to_number)
    else:
        working["_days_in_mls"] = None

    if subtype_col:
        working["_property_subtype"] = working[subtype_col].astype(str)
    else:
        working["_property_subtype"] = ""

    if levels_col:
        working["_levels"] = working[levels_col].astype(str)
    else:
        working["_levels"] = ""

    if subdivision_col:
        working["_subdivision"] = working[subdivision_col].astype(str)
    else:
        working["_subdivision"] = ""

    if association_name_col:
        working["_association_name"] = working[association_name_col].astype(str)
    else:
        working["_association_name"] = ""

    if association_name_2_col:
        working["_association_name_2"] = working[association_name_2_col].astype(str)
    else:
        working["_association_name_2"] = ""

    if association_fee_col:
        working["_association_fee_total_annual"] = working[association_fee_col].apply(_to_number)
    else:
        working["_association_fee_total_annual"] = None

    if status_col:
        working["_status_text"] = working[status_col].astype(str).str.lower()
    else:
        working["_status_text"] = ""
        warnings.append(
            "MLS status column was not detected; rows with usable close prices will be treated as closed evidence."
        )

    working["_address"] = working.apply(lambda row: _row_address(row, column_map), axis=1)
    working["_net_price"] = working["_close_price"] - working["_concessions"]

    all_prepared_df = working.copy()

    usable_price_df = working[
        working["_close_price"].notna()
        & (working["_close_price"] > 0)
        & working["_net_price"].notna()
        & (working["_net_price"] > 0)
    ].copy()

    if usable_price_df.empty:
        return {
            "all_prepared_df": all_prepared_df,
            "closed_df": pd.DataFrame(),
            "comp_candidates_df": pd.DataFrame(),
        }

    if status_col:
        closed_mask = (
            usable_price_df["_status_text"].str.contains("closed")
            | usable_price_df["_status_text"].str.contains("sold")
            | usable_price_df["_status_text"].str.contains("settled")
        )

        closed_df = usable_price_df[closed_mask].copy()

        if closed_df.empty:
            closed_df = usable_price_df.copy()
            warnings.append(
                "No rows clearly marked Closed/Sold were detected; using rows with usable close prices."
            )
    else:
        closed_df = usable_price_df.copy()

    comp_candidates_df = _filter_comp_candidates(
        closed_df=closed_df,
        subject=subject,
        warnings=warnings,
        notes=notes,
    )

    return {
        "all_prepared_df": all_prepared_df,
        "closed_df": closed_df,
        "comp_candidates_df": comp_candidates_df,
    }


def _filter_comp_candidates(
    closed_df: pd.DataFrame,
    subject: Dict[str, Any],
    warnings: List[str],
    notes: List[str],
) -> pd.DataFrame:
    working = closed_df.copy()

    subject_above_grade = subject.get("above_grade_sqft")
    subject_levels = _normalize_level(subject.get("levels"))

    if subject_above_grade:
        low = subject_above_grade * 0.85
        high = subject_above_grade * 1.10

        working["_within_size_window"] = working["_above_grade_sqft"].apply(
            lambda x: bool(x is not None and not pd.isna(x) and low <= x <= high)
        )
        working["_size_diff_pct"] = working["_above_grade_sqft"].apply(
            lambda x: _safe_pct_diff(x, subject_above_grade)
        )

        size_filtered = working[working["_within_size_window"]].copy()

        if len(size_filtered) >= 3:
            working = size_filtered
            notes.append(
                f"Applied 85% to 110% above-grade size filter: {round(low)} to {round(high)} sqft."
            )
        elif len(size_filtered) > 0:
            working = size_filtered
            warnings.append(
                f"Only {len(size_filtered)} comps remained after 85% to 110% above-grade filtering."
            )
        else:
            warnings.append(
                "No comps remained after 85% to 110% above-grade filtering; using all closed comps as backup candidates."
            )
    else:
        working["_within_size_window"] = False
        working["_size_diff_pct"] = None
        notes.append("Above-grade size filter was not applied because subject square footage was missing.")

    if subject_levels:
        working["_level_match"] = working["_levels"].apply(
            lambda value: _levels_match(subject_levels, value)
        )

        level_filtered = working[working["_level_match"]].copy()

        if len(level_filtered) >= 3:
            working = level_filtered
            notes.append("Applied like-level/style filter because at least 3 matching closed comps were available.")
        elif len(level_filtered) > 0:
            working = level_filtered
            warnings.append(
                f"Only {len(level_filtered)} comps matched subject level/style; using those as best available."
            )
        else:
            warnings.append(
                "No closed comps matched subject level/style; using size-filtered or available closed comps as backup."
            )
    else:
        working["_level_match"] = False
        notes.append("Like-level/style filter was not applied because subject level/style was missing.")

    return working.copy()


# ---------------------------------------------------------------------
# Adjustments and scoring
# ---------------------------------------------------------------------

def _apply_adjustments_and_scoring(
    comp_df: pd.DataFrame,
    subject: Dict[str, Any],
    one_hundred_four_mc_summary: Dict[str, Any],
    warnings: List[str],
    notes: List[str],
) -> pd.DataFrame:
    working = comp_df.copy()

    effective_date = _determine_effective_date(working)
    monthly_market_change = _to_number(
        one_hundred_four_mc_summary.get("monthly_market_change_percent")
    )

    time_adjustments_enabled = (
        monthly_market_change is not None
        and abs(monthly_market_change) >= 0.25
        and "_close_date" in working.columns
    )

    if time_adjustments_enabled:
        notes.append(
            f"Time adjustment enabled using 1004MC monthly market change of {monthly_market_change}%."
        )
    else:
        notes.append(
            "Time adjustment not applied unless 1004MC monthly market change is supplied and meaningful."
        )

    rows = []

    for _idx, row in working.iterrows():
        net_price = _to_number(row.get("_net_price")) or 0

        above_grade_adj = _sf_adjustment(
            subject.get("above_grade_sqft"),
            row.get("_above_grade_sqft"),
            ADJUSTMENT_RATES["above_grade_sqft"],
        )

        finished_basement_adj = _sf_adjustment(
            subject.get("finished_basement_sqft"),
            row.get("_finished_basement_sqft"),
            ADJUSTMENT_RATES["finished_basement_sqft"],
        )

        unfinished_basement_adj = _sf_adjustment(
            subject.get("unfinished_basement_sqft"),
            row.get("_unfinished_basement_sqft"),
            ADJUSTMENT_RATES["unfinished_basement_sqft"],
        )

        time_adjustment = 0

        if time_adjustments_enabled:
            time_adjustment = _calculate_time_adjustment(
                net_price=net_price,
                close_date=row.get("_close_date"),
                effective_date=effective_date,
                monthly_market_change_percent=monthly_market_change,
            )

        total_adjustments = (
            above_grade_adj
            + finished_basement_adj
            + unfinished_basement_adj
            + time_adjustment
        )

        adjusted_price = net_price + total_adjustments

        score, score_notes = _score_comp(row, subject, effective_date)

        row_dict = row.to_dict()
        row_dict.update(
            {
                "_above_grade_adjustment": above_grade_adj,
                "_finished_basement_adjustment": finished_basement_adj,
                "_unfinished_basement_adjustment": unfinished_basement_adj,
                "_time_adjustment": time_adjustment,
                "_total_adjustments": total_adjustments,
                "_adjusted_price": adjusted_price,
                "_comp_score": score,
                "_comp_score_notes": score_notes,
            }
        )

        rows.append(row_dict)

    adjusted = pd.DataFrame(rows)

    adjusted = adjusted.sort_values(
        by=["_comp_score", "_within_size_window", "_adjusted_price"],
        ascending=[False, False, True],
        na_position="last",
    ).copy()

    return adjusted


def _select_best_comps(adjusted_df: pd.DataFrame, notes: List[str]) -> pd.DataFrame:
    if adjusted_df.empty:
        return adjusted_df

    usable = adjusted_df[
        adjusted_df["_adjusted_price"].notna()
        & (adjusted_df["_adjusted_price"] > 0)
    ].copy()

    if usable.empty:
        return adjusted_df.head(0)

    strong = usable[usable["_comp_score"] >= 60].copy()

    if len(strong) >= 3:
        selected = strong.head(6).copy()
        notes.append(f"Selected {len(selected)} comps with score of 60 or higher.")
        return selected

    selected = usable.head(min(6, len(usable))).copy()
    notes.append(
        f"Fewer than 3 comps scored 60 or higher. Selected best {len(selected)} available comps."
    )
    return selected


def _score_comp(
    row: pd.Series,
    subject: Dict[str, Any],
    effective_date: Optional[pd.Timestamp],
) -> Tuple[float, List[str]]:
    score = 100.0
    score_notes: List[str] = []

    subject_ag = subject.get("above_grade_sqft")
    comp_ag = _to_number(row.get("_above_grade_sqft"))

    if subject_ag and comp_ag:
        pct_diff = abs(comp_ag - subject_ag) / subject_ag

        if pct_diff <= 0.10:
            score_notes.append("strong size match")
        elif pct_diff <= 0.20:
            score_notes.append("moderate size difference")
            score -= 8
        else:
            score_notes.append("larger size difference")
            score -= min(30, pct_diff * 100)

        if not row.get("_within_size_window"):
            score -= 8
    else:
        score -= 12
        score_notes.append("missing size comparison")

    if row.get("_level_match") is True:
        score_notes.append("like-level/style match")
    elif _normalize_level(subject.get("levels")):
        score -= 8
        score_notes.append("level/style not confirmed as match")

    subject_year = _to_number(subject.get("year_built"))
    comp_year = _to_number(row.get("_year_built"))

    if subject_year and comp_year:
        year_diff = abs(subject_year - comp_year)

        if year_diff <= 10:
            score_notes.append("similar year built")
        elif year_diff <= 25:
            score -= 5
            score_notes.append("moderate age difference")
        else:
            score -= 10
            score_notes.append("larger age difference")

    subject_basement = _to_number(subject.get("basement_sqft"))
    comp_basement = _to_number(row.get("_basement_sqft"))

    if subject_basement is not None and comp_basement is not None:
        basement_diff = abs(subject_basement - comp_basement)

        if basement_diff <= 250:
            score_notes.append("similar basement size")
        elif basement_diff <= 750:
            score -= 4
            score_notes.append("moderate basement difference")
        else:
            score -= 8
            score_notes.append("larger basement difference")

    subject_subtype = _normalize_property_subtype(subject.get("property_subtype"))
    comp_subtype = _normalize_property_subtype(row.get("_property_subtype"))

    if subject_subtype and comp_subtype:
        if subject_subtype == comp_subtype:
            score_notes.append("similar property subtype")
        else:
            score -= 8
            score_notes.append("property subtype differs")

    close_date = row.get("_close_date")

    if effective_date is not None and close_date is not None and not pd.isna(close_date):
        months_old = abs(_months_between(close_date, effective_date))

        if months_old <= 3:
            score_notes.append("recent sale")
        elif months_old <= 6:
            score -= 3
            score_notes.append("moderately recent sale")
        elif months_old <= 12:
            score -= 7
            score_notes.append("older sale")
        else:
            score -= 12
            score_notes.append("sale over 12 months old")

    score = max(0, min(100, score))

    return round(score, 2), score_notes


# ---------------------------------------------------------------------
# Output calculations
# ---------------------------------------------------------------------

def _calculate_online_estimated_value(subject_profile: Dict[str, Any]) -> Dict[str, Any]:
    values = []

    zillow = _first_number(subject_profile, ["zillow_estimate", "zestimate"])
    redfin = _first_number(subject_profile, ["redfin_estimate"])
    real_avm = _first_number(subject_profile, ["real_avm", "RealAVM"])

    if zillow:
        values.append(("Zillow", zillow))

    if redfin:
        values.append(("Redfin", redfin))

    if real_avm:
        values.append(("RealAVM", real_avm))

    numeric_values = [value for _name, value in values]

    sources_found = len(values)

    if sources_found == 0:
        label = "Based on 0 of 3 online estimated values found"
    elif sources_found == 1:
        label = "Based on 1 of 3 online estimated values found"
    elif sources_found == 2:
        label = "Based on 2 of 3 online estimated values found"
    else:
        label = "Based on 3 of 3 online estimated values found"

    return {
        "display_label": "Online Estimated Value",
        "zillow_estimate": _round_money(zillow),
        "redfin_estimate": _round_money(redfin),
        "real_avm": _round_money(real_avm),
        "sources_found": sources_found,
        "sources_possible": 3,
        "sources_used": [name for name, _value in values],
        "source_count_label": label,
        "range_low": _round_money(min(numeric_values)) if numeric_values else None,
        "range_high": _round_money(max(numeric_values)) if numeric_values else None,
        "range_width": (
            _round_money(max(numeric_values) - min(numeric_values))
            if numeric_values
            else None
        ),
        "basis": "Lowest to highest available online estimated values.",
        "requires_gpt_comparison_to_comps": True,
    }


def _calculate_selected_comparable_evidence_range(
    selected_df: pd.DataFrame,
    warnings: List[str],
    notes: List[str],
) -> Dict[str, Any]:
    adjusted_prices = _clean_numeric_list(selected_df["_adjusted_price"].tolist())
    net_prices = _clean_numeric_list(selected_df["_net_price"].tolist())

    if not adjusted_prices:
        warnings.append("No adjusted prices were available for Selected Comparable Evidence Range.")
        return {
            "display_label": "Selected Comparable Evidence Range",
            "range_low": None,
            "range_high": None,
            "range_width": None,
            "basis": "Not available.",
            "requires_gpt_qualification": True,
        }

    notes.append(
        "Selected Comparable Evidence Range is based on the lowest to highest total adjusted price among selected comps."
    )

    return {
        "display_label": "Selected Comparable Evidence Range",
        "raw_net_price_low": _round_money(min(net_prices)) if net_prices else None,
        "raw_net_price_high": _round_money(max(net_prices)) if net_prices else None,
        "range_low": _round_money(min(adjusted_prices)),
        "range_high": _round_money(max(adjusted_prices)),
        "range_width": _round_money(max(adjusted_prices) - min(adjusted_prices)),
        "basis": "Lowest to highest total adjusted price among selected comparable sales.",
        "not_final_market_entry_range": True,
        "requires_gpt_qualification": True,
    }


def _calculate_comp_statistics(selected_df: pd.DataFrame) -> Dict[str, Any]:
    adjusted_prices = _clean_numeric_list(selected_df["_adjusted_price"].tolist())
    net_prices = _clean_numeric_list(selected_df["_net_price"].tolist())
    scores = _clean_numeric_list(selected_df["_comp_score"].tolist())

    weighted_adjusted_average = _weighted_average(
        values=adjusted_prices,
        weights=[max(score, 10) for score in scores],
    )

    return {
        "selected_comp_count": int(len(selected_df)),
        "lowest_net_price": _round_money(min(net_prices)) if net_prices else None,
        "highest_net_price": _round_money(max(net_prices)) if net_prices else None,
        "median_net_price": _round_money(_median(net_prices)),
        "average_net_price": _round_money(_average(net_prices)),
        "lowest_adjusted_price": _round_money(min(adjusted_prices)) if adjusted_prices else None,
        "highest_adjusted_price": _round_money(max(adjusted_prices)) if adjusted_prices else None,
        "median_adjusted_price": _round_money(_median(adjusted_prices)),
        "average_adjusted_price": _round_money(_average(adjusted_prices)),
        "weighted_adjusted_average": _round_money(weighted_adjusted_average),
        "average_comp_score": round(_average(scores), 2) if scores else None,
        "interpretation_note": (
            "Average and median are retained as evidence indicators only. "
            "They are not final value conclusions without GPT/Realtor qualification."
        ),
    }



def _is_closed_status_series(status: pd.Series) -> pd.Series:
    status = status.fillna("").astype(str).str.lower().str.strip()
    return (
        status.str.contains("closed", na=False)
        | status.str.contains("sold", na=False)
        | status.str.contains("settled", na=False)
    )


def _is_pending_status_series(status: pd.Series) -> pd.Series:
    status = status.fillna("").astype(str).str.lower().str.strip()
    closed_mask = _is_closed_status_series(status)
    return (
        (
            status.str.contains("pending", na=False)
            | status.str.contains("under contract", na=False)
        )
        & ~closed_mask
    )


def _is_active_status_series(status: pd.Series) -> pd.Series:
    status = status.fillna("").astype(str).str.lower().str.strip()
    closed_mask = _is_closed_status_series(status)
    pending_mask = _is_pending_status_series(status)
    coming_soon_mask = status.str.contains("coming soon", na=False) & ~pending_mask & ~closed_mask
    return (
        status.str.contains("active", na=False)
        & ~pending_mask
        & ~closed_mask
        & ~coming_soon_mask
    )


def _pct(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    if not whole:
        return None
    try:
        return round((float(part or 0) / float(whole)) * 100.0, 1)
    except Exception:
        return None


def _round_currency_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return int(round(float(value)))
    except Exception:
        return None


def _format_price_sensitivity_level(reduction_rate: Optional[float], net_below_rate: Optional[float], concession_rate: Optional[float], dim_gap: Optional[float]) -> str:
    """Classify market acceptance pressure without forcing an automatic price cut."""
    score = 0
    if reduction_rate is not None:
        if reduction_rate >= 55:
            score += 2
        elif reduction_rate >= 40:
            score += 1
    if net_below_rate is not None:
        if net_below_rate >= 75:
            score += 2
        elif net_below_rate >= 60:
            score += 1
    if concession_rate is not None:
        if concession_rate >= 60:
            score += 2
        elif concession_rate >= 40:
            score += 1
    if dim_gap is not None:
        if dim_gap >= 35:
            score += 2
        elif dim_gap >= 20:
            score += 1

    if score >= 6:
        return "Strong price sensitivity / repositioning review recommended if early buyer activity is weak"
    if score >= 4:
        return "Moderate price sensitivity / monitor early activity closely"
    if score >= 2:
        return "Mild price sensitivity / market acceptance should be watched"
    return "Low price sensitivity signal from available data"


def _calculate_price_reduction_metrics(rows: pd.DataFrame) -> Dict[str, Any]:
    if rows is None or rows.empty:
        return {
            "count": 0,
            "price_reduction_count": 0,
            "price_reduction_rate_percent": None,
            "average_reduction_amount_when_reduced": None,
            "median_reduction_amount_when_reduced": None,
            "average_dim_reduced": None,
            "average_dim_not_reduced": None,
        }

    working = rows.copy()
    if "_list_price" not in working.columns or "_original_list_price" not in working.columns:
        return {"count": int(len(working)), "status": "missing_list_or_original_list_price"}

    working["_price_reduction_amount"] = working["_original_list_price"] - working["_list_price"]
    reduced = working[working["_price_reduction_amount"] > 0].copy()
    not_reduced = working[~(working["_price_reduction_amount"] > 0)].copy()

    reduced_amounts = _clean_numeric_list(reduced["_price_reduction_amount"].tolist()) if not reduced.empty else []

    return {
        "count": int(len(working)),
        "price_reduction_count": int(len(reduced)),
        "price_reduction_rate_percent": _pct(len(reduced), len(working)),
        "average_reduction_amount_when_reduced": _round_currency_or_none(_average(reduced_amounts)),
        "median_reduction_amount_when_reduced": _round_currency_or_none(pd.Series(reduced_amounts).median()) if reduced_amounts else None,
        "average_dim_reduced": _round_number(_average(_clean_numeric_list(reduced["_days_in_mls"].tolist()))) if not reduced.empty and "_days_in_mls" in reduced.columns else None,
        "average_dim_not_reduced": _round_number(_average(_clean_numeric_list(not_reduced["_days_in_mls"].tolist()))) if not not_reduced.empty and "_days_in_mls" in not_reduced.columns else None,
    }


def _net_result_bucket(amount_below_original: Optional[float]) -> str:
    if amount_below_original is None:
        return "Unknown"
    if amount_below_original <= 0:
        return "At / above original"
    if amount_below_original < 10000:
        return "$1-$9,999 below"
    if amount_below_original < 25000:
        return "$10K-$24,999 below"
    if amount_below_original < 50000:
        return "$25K-$49,999 below"
    return "$50K+ below"


def _build_net_result_buckets(closed_rows: pd.DataFrame) -> List[Dict[str, Any]]:
    buckets_order = [
        "At / above original",
        "$1-$9,999 below",
        "$10K-$24,999 below",
        "$25K-$49,999 below",
        "$50K+ below",
        "Unknown",
    ]
    if closed_rows is None or closed_rows.empty:
        return []

    working = closed_rows.copy()
    working["_net_below_original_amount"] = working["_original_list_price"] - working["_net_price"]
    working["_net_result_bucket"] = working["_net_below_original_amount"].apply(_net_result_bucket)

    output: List[Dict[str, Any]] = []
    total = len(working)
    for bucket in buckets_order:
        subset = working[working["_net_result_bucket"] == bucket]
        if subset.empty:
            continue
        output.append(
            {
                "net_result_vs_original": bucket,
                "sales": int(len(subset)),
                "share_percent": _pct(len(subset), total),
                "average_dim": _round_number(_average(_clean_numeric_list(subset["_days_in_mls"].tolist()))) if "_days_in_mls" in subset.columns else None,
            }
        )
    return output


def _calculate_price_sensitivity_and_seller_net_behavior(
    all_prepared_df: pd.DataFrame,
    source_label: str = "1004MC / Competition Market File",
) -> Dict[str, Any]:
    """Analyze list-price reductions, concessions, seller-net movement, and market acceptance.

    This is separate from Market Momentum. Momentum answers how fast the market is moving.
    Price Sensitivity answers how much sellers are having to adjust before buyers accept a deal.
    """
    if all_prepared_df is None or all_prepared_df.empty or "_status_text" not in all_prepared_df.columns:
        return {
            "section_label": "Price Sensitivity & Seller Net Behavior",
            "status": "not_available",
            "source": source_label,
            "seller_facing_note": "Price sensitivity could not be calculated because the market file was missing usable status data.",
        }

    df = all_prepared_df.copy()
    status = df["_status_text"].fillna("").astype(str).str.lower().str.strip()
    closed_mask = _is_closed_status_series(status)
    pending_mask = _is_pending_status_series(status)
    active_mask = _is_active_status_series(status)

    closed_rows = df[closed_mask].copy()
    if closed_rows.empty:
        return {
            "section_label": "Price Sensitivity & Seller Net Behavior",
            "status": "not_available",
            "source": source_label,
            "seller_facing_note": "Price sensitivity could not be calculated because no Closed/Sold rows were available.",
        }

    close_dates = pd.to_datetime(closed_rows.get("_close_date"), errors="coerce") if "_close_date" in closed_rows.columns else pd.Series([], dtype="datetime64[ns]")
    usable_close_dates = close_dates.dropna()

    latest_close_date = usable_close_dates.max() if not usable_close_dates.empty else None
    if latest_close_date is not None:
        latest_90_start = latest_close_date - pd.Timedelta(days=89)
        last_90_mask = close_dates.between(latest_90_start, latest_close_date, inclusive="both")
        closed_last_90 = closed_rows[last_90_mask].copy()
    else:
        latest_90_start = None
        closed_last_90 = closed_rows.copy()

    active_metrics = _calculate_price_reduction_metrics(df[active_mask].copy())
    pending_metrics = _calculate_price_reduction_metrics(df[pending_mask].copy())
    closed_90_metrics = _calculate_price_reduction_metrics(closed_last_90)

    # Closed sale price/net behavior in the most recent 90 days.
    reviewed_count = int(len(closed_last_90))
    closed_below_original_mask = closed_last_90["_close_price"] < closed_last_90["_original_list_price"] if "_close_price" in closed_last_90.columns and "_original_list_price" in closed_last_90.columns else pd.Series([], dtype=bool)
    net_below_original_mask = closed_last_90["_net_price"] < closed_last_90["_original_list_price"] if "_net_price" in closed_last_90.columns and "_original_list_price" in closed_last_90.columns else pd.Series([], dtype=bool)
    concessions_mask = closed_last_90["_concessions"] > 0 if "_concessions" in closed_last_90.columns else pd.Series([], dtype=bool)

    concession_amounts = _clean_numeric_list(closed_last_90.loc[concessions_mask, "_concessions"].tolist()) if reviewed_count and "_concessions" in closed_last_90.columns else []

    reduced_dim = closed_90_metrics.get("average_dim_reduced")
    non_reduced_dim = closed_90_metrics.get("average_dim_not_reduced")
    dim_gap = (reduced_dim - non_reduced_dim) if reduced_dim is not None and non_reduced_dim is not None else None

    reduction_rate = closed_90_metrics.get("price_reduction_rate_percent")
    net_below_rate = _pct(int(net_below_original_mask.sum()) if len(net_below_original_mask) else 0, reviewed_count) if reviewed_count else None
    concession_rate = _pct(int(concessions_mask.sum()) if len(concessions_mask) else 0, reviewed_count) if reviewed_count else None

    sensitivity_level = _format_price_sensitivity_level(reduction_rate, net_below_rate, concession_rate, dim_gap)

    return compact_dict_local(
        {
            "section_label": "Price Sensitivity & Seller Net Behavior",
            "status": "calculated",
            "source": source_label,
            "purpose": (
                "Separate from Market Momentum. Momentum measures speed/activity. Price Sensitivity measures how often sellers had to reposition, concede, or net below original list before buyers accepted the property."
            ),
            "closed_sales_window": "Most recent 90 days by Close Date",
            "closed_sales_reviewed": reviewed_count,
            "latest_90_start_date": latest_90_start.date().isoformat() if latest_90_start is not None else None,
            "latest_90_end_date": latest_close_date.date().isoformat() if latest_close_date is not None else None,
            "active_price_adjustment_behavior": active_metrics,
            "pending_price_adjustment_behavior": pending_metrics,
            "closed_last_90_price_adjustment_behavior": closed_90_metrics,
            "closed_below_original_count": int(closed_below_original_mask.sum()) if len(closed_below_original_mask) else None,
            "closed_below_original_rate_percent": _pct(int(closed_below_original_mask.sum()) if len(closed_below_original_mask) else 0, reviewed_count) if reviewed_count else None,
            "net_below_original_count": int(net_below_original_mask.sum()) if len(net_below_original_mask) else None,
            "net_below_original_rate_percent": net_below_rate,
            "seller_concession_count": int(concessions_mask.sum()) if len(concessions_mask) else None,
            "seller_concession_rate_percent": concession_rate,
            "average_concession_when_present": _round_currency_or_none(_average(concession_amounts)) if concession_amounts else None,
            "average_dim_gap_reduced_vs_not_reduced": _round_number(dim_gap) if dim_gap is not None else None,
            "seller_net_result_buckets": _build_net_result_buckets(closed_last_90),
            "price_sensitivity_level": sensitivity_level,
            "repositioning_consideration": (
                "This is not an automatic price reduction. It is a market-acceptance review. If early buyer activity is weak, use the reduction rate, concessions, net-below-original behavior, active competition, and condition/terms feedback to decide whether a tactical repositioning is warranted."
            ),
            "seller_psychology_note": (
                "Sellers often worry that lowering price signals weakness. A late reduction after long market time can create that perception. An early, data-supported repositioning can be framed as a strategy to return the home to the strongest buyer-search lane before it becomes stale."
            ),
            "summary_for_momentum": (
                f"Closed last 90 reviewed: {reviewed_count}; MLS reduction rate: {reduction_rate}%; net below original: {net_below_rate}%; seller concessions: {concession_rate}%; signal: {sensitivity_level}."
                if reviewed_count else None
            ),
        }
    )


def compact_dict_local(data: Dict[str, Any]) -> Dict[str, Any]:
    """Local compact helper for valuation-engine calculation dictionaries."""
    output: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        output[key] = value
    return output

def _calculate_limited_market_momentum(
    all_prepared_df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
    notes: List[str],
) -> Dict[str, Any]:
    if all_prepared_df.empty or "_status_text" not in all_prepared_df.columns:
        return {
            "section_label": "Market Momentum & Buyer Competition",
            "status": "not_available",
            "source": "current comparable evidence file only",
            "note": (
                "A separate competitive market snapshot is recommended for full Shopping Cart Theory analysis."
            ),
            "requires_gpt_interpretation": True,
        }

    df = all_prepared_df.copy()
    status = df["_status_text"].fillna("").astype(str).str.lower().str.strip()

    closed_mask = (
        status.str.contains("closed", na=False)
        | status.str.contains("sold", na=False)
        | status.str.contains("settled", na=False)
    )
    pending_mask = (
        (
            status.str.contains("pending", na=False)
            | status.str.contains("under contract", na=False)
        )
        & ~closed_mask
    )
    coming_soon_mask = status.str.contains("coming soon", na=False) & ~pending_mask & ~closed_mask
    active_mask = (
        status.str.contains("active", na=False)
        & ~pending_mask
        & ~closed_mask
        & ~coming_soon_mask
    )

    active_count = int(active_mask.sum())
    coming_soon_count = int(coming_soon_mask.sum())
    pending_count = int(pending_mask.sum())
    closed_count = int(closed_mask.sum())

    solds = df[closed_mask].copy()

    closed_sales_pace = _calculate_closed_sales_pace_from_dates(solds)

    average_monthly_closed_sales = closed_sales_pace.get("average_monthly_closed_sales")
    closed_sales_months_covered = closed_sales_pace.get("closed_sales_months_covered")

    pending_inclusive_monthly_demand = (
        (average_monthly_closed_sales or 0) + pending_count
        if (average_monthly_closed_sales or pending_count)
        else None
    )

    current_demand_pressure_moi = (
        active_count / pending_inclusive_monthly_demand
        if active_count and pending_inclusive_monthly_demand
        else None
    )

    primary_months_of_inventory = (
        active_count / average_monthly_closed_sales
        if active_count and average_monthly_closed_sales
        else None
    )

    # Backward-compatible aliases:
    # - projected_moi_closed_only is the primary seller-facing MOI.
    # - projected_moi_absorption_weighted is retained only as a secondary
    #   pending-inclusive demand-pressure indicator because older code may read it.
    projected_moi_closed_only = primary_months_of_inventory
    projected_moi_absorption_weighted = current_demand_pressure_moi
    absorption_weighted_monthly_demand = pending_inclusive_monthly_demand

    avg_original_list = (
        _average(_clean_numeric_list(solds["_original_list_price"].tolist()))
        if not solds.empty and "_original_list_price" in solds.columns
        else None
    )
    avg_sale = (
        _average(_clean_numeric_list(solds["_close_price"].tolist()))
        if not solds.empty and "_close_price" in solds.columns
        else None
    )

    list_to_sale_ratio = (
        avg_sale / avg_original_list
        if avg_original_list and avg_sale
        else None
    )

    notes.append(
        "Market Momentum uses Closed sales from the most recent 90 days and divides by 3 for current absorption, while retaining the full-year monthly rhythm for trend context."
    )

    return {
        "section_label": "Market Momentum & Buyer Competition",
        "status": "limited_from_current_upload",
        "source": "current comparable evidence file only",
        "important_limitation": (
            "Comparable sales and competitive market data are related but not identical. "
            "A property may be active competition without being a valid comparable sale. "
            "A separate active/pending competitive market file is recommended for a fuller competition review."
        ),
        "seller_meaning_rule": (
            "Explain competition through Pricing, Condition, Terms, and Timing. Active listings show the choices buyers have today; "
            "closed comparable sales support value, but active competition affects showing traffic, negotiation leverage, and how quickly the seller may need to respond."
        ),
        "closed_sales_pace_rule": (
            "Average monthly closed sales are calculated from Closed sales in the most recent 90 days divided by 3. "
            "The annual Closed pull remains available for month-by-month rhythm/trend review, but the primary seller-facing Months of Inventory uses the current 90-day Closed sales pace."
        ),
        "moi_reporting_rule": (
            "Primary seller-facing MOI = Active listings ÷ latest 90-day average monthly Closed sales. "
            "The pending-inclusive formula is a secondary current-demand pressure indicator only; do not present it as the main MOI."
        ),
        "time_frame_assumption": "Closed sales pace for absorption is based on the latest 90 days of Closed records when Close Date is supplied; otherwise the report must state the limitation.",
        "active_count": active_count,
        "coming_soon_count": coming_soon_count,
        "pending_count": pending_count,
        "closed_count": closed_count,
        "closed_count_total_0_365_pull": closed_sales_pace.get("closed_count_total_0_365_pull") or closed_count,
        "closed_count_last_90_days": closed_sales_pace.get("closed_count_last_90_days"),
        "recent_90_day_start_date": closed_sales_pace.get("recent_90_day_start_date"),
        "recent_90_day_end_date": closed_sales_pace.get("recent_90_day_end_date"),
        "recent_90_day_months_used": closed_sales_pace.get("recent_90_day_months_used"),
        "monthly_closed_sales_rhythm": closed_sales_pace.get("monthly_closed_sales_rhythm"),
        "closed_sales_min_close_date": closed_sales_pace.get("min_close_date"),
        "closed_sales_max_close_date": closed_sales_pace.get("max_close_date"),
        "closed_sales_date_span_days": closed_sales_pace.get("date_span_days"),
        "closed_sales_months_covered": closed_sales_months_covered,
        "closed_sales_months_covered_rounded": (
            round(closed_sales_months_covered, 2)
            if closed_sales_months_covered is not None
            else None
        ),
        "average_monthly_closed_sales": (
            round(average_monthly_closed_sales, 2)
            if average_monthly_closed_sales is not None
            else None
        ),
        "closed_sales_pace_source": closed_sales_pace.get("source"),
        "primary_months_of_inventory": (
            round(primary_months_of_inventory, 2)
            if primary_months_of_inventory is not None
            else None
        ),
        "primary_moi_formula": "Active listings ÷ latest 90-day average monthly Closed sales",
        "pending_inclusive_monthly_demand": (
            round(pending_inclusive_monthly_demand, 2)
            if pending_inclusive_monthly_demand is not None
            else None
        ),
        "current_demand_pressure_moi": (
            round(current_demand_pressure_moi, 2)
            if current_demand_pressure_moi is not None
            else None
        ),
        "current_demand_pressure_formula": "Active listings ÷ (Pending listings + latest 90-day average monthly Closed sales)",
        "absorption_weighted_monthly_demand": (
            round(absorption_weighted_monthly_demand, 2)
            if absorption_weighted_monthly_demand is not None
            else None
        ),
        "projected_moi_absorption_weighted": (
            round(projected_moi_absorption_weighted, 2)
            if projected_moi_absorption_weighted is not None
            else None
        ),
        "projected_moi_closed_only": (
            round(projected_moi_closed_only, 2)
            if projected_moi_closed_only is not None
            else None
        ),
        "projected_moi_range": (
            {
                "primary_seller_facing_moi": round(primary_months_of_inventory, 2),
                "secondary_pending_pressure_moi": round(current_demand_pressure_moi, 2),
                "seller_facing_note": (
                    "Use the Closed-only MOI as the primary seller-facing supply/absorption number because it is more conservative and easier to explain. "
                    "The pending-inclusive number is secondary; it may show near-term demand pressure, but it should not replace the main MOI in seller guidance."
                ),
            }
            if current_demand_pressure_moi is not None and primary_months_of_inventory is not None
            else None
        ),
        "average_original_list_price_of_solds": _round_money(avg_original_list),
        "average_sale_price_of_solds": _round_money(avg_sale),
        "list_to_sale_ratio": round(list_to_sale_ratio, 4) if list_to_sale_ratio else None,
        "list_to_sale_ratio_percent": round(list_to_sale_ratio * 100, 2) if list_to_sale_ratio else None,
        "average_dim_active": (
            _round_number(_average(_clean_numeric_list(df[active_mask]["_days_in_mls"].tolist())))
            if active_count and "_days_in_mls" in df.columns
            else None
        ),
        "average_dim_pending": (
            _round_number(_average(_clean_numeric_list(df[pending_mask]["_days_in_mls"].tolist())))
            if pending_count and "_days_in_mls" in df.columns
            else None
        ),
        "average_dim_closed": (
            _round_number(_average(_clean_numeric_list(df[closed_mask]["_days_in_mls"].tolist())))
            if closed_count and "_days_in_mls" in df.columns
            else None
        ),
        "requires_gpt_interpretation": True,
    }


def _calculate_closed_sales_pace_from_dates(solds: pd.DataFrame) -> Dict[str, Any]:
    """Calculate current closed-sales pace from the most recent 90 days.

    The broader 1004MC / Competition file may contain up to 365 days of Closed
    records. That annual pull remains useful for month-by-month rhythm/trend
    review, but absorption/MOI should use the most current rhythm:
    Closed sales in the latest 90-day window divided by 3.
    """
    if solds is None or solds.empty:
        return {
            "closed_count": 0,
            "closed_count_last_90_days": 0,
            "average_monthly_closed_sales": None,
            "recent_90_day_months_used": 3,
            "source": "no_closed_sales",
        }

    closed_count_total = int(len(solds))

    if "_close_date" not in solds.columns:
        return {
            "closed_count": closed_count_total,
            "closed_count_last_90_days": None,
            "average_monthly_closed_sales": None,
            "recent_90_day_months_used": 3,
            "source": "missing_close_date_column",
            "note": "Close Date was not available, so last-90-day closed-sales pace could not be calculated safely.",
        }

    close_dates = pd.to_datetime(solds["_close_date"], errors="coerce")
    usable_close_dates = close_dates.dropna()

    if usable_close_dates.empty:
        return {
            "closed_count": closed_count_total,
            "closed_count_last_90_days": None,
            "average_monthly_closed_sales": None,
            "recent_90_day_months_used": 3,
            "source": "no_usable_close_dates",
            "note": "Closed rows were present, but usable Close Date values were not available.",
        }

    min_close_date = usable_close_dates.min()
    max_close_date = usable_close_dates.max()

    latest_90_start = max_close_date - pd.Timedelta(days=89)
    last_90_mask = close_dates.between(latest_90_start, max_close_date, inclusive="both")
    closed_last_90 = solds[last_90_mask].copy()
    closed_count_last_90 = int(len(closed_last_90))

    average_monthly_closed_sales = closed_count_last_90 / 3.0

    monthly_rhythm_series = (
        usable_close_dates.dt.to_period("M")
        .value_counts()
        .sort_index()
    )
    monthly_rhythm = [
        {
            "month": str(month),
            "closed_count": int(count),
        }
        for month, count in monthly_rhythm_series.items()
    ]

    return {
        "closed_count": closed_count_total,
        "closed_count_total_0_365_pull": closed_count_total,
        "closed_count_last_90_days": closed_count_last_90,
        "recent_90_day_start_date": latest_90_start.date().isoformat(),
        "recent_90_day_end_date": max_close_date.date().isoformat(),
        "recent_90_day_months_used": 3,
        "min_close_date": min_close_date.date().isoformat(),
        "max_close_date": max_close_date.date().isoformat(),
        "date_span_days": max(int((max_close_date - min_close_date).days), 0),
        "closed_sales_months_covered": 3.0,
        "average_monthly_closed_sales": average_monthly_closed_sales,
        "monthly_closed_sales_rhythm": monthly_rhythm,
        "source": "latest_90_days_divided_by_3",
        "seller_facing_note": (
            "The file may contain up to one year of Closed sales, but absorption uses the most recent 90 days. "
            "Closed sales in that 90-day window are divided by 3 to reflect the current market rhythm."
        ),
    }



def _summarize_1004mc(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "is_supplied": bool(
            summary.get("is_supplied")
            or summary.get("recommended_route") == "parsed_1004mc_coordinate_table"
            or summary.get("current_3_sales") is not None
        ),
        "source_status": summary.get("source_status") or summary.get("recommended_route"),
        "parser_confidence": summary.get("parser_confidence"),
        "annual_market_change_percent": summary.get("annual_market_change_percent"),
        "monthly_market_change_percent": summary.get("monthly_market_change_percent"),
        "market_trend_classification": summary.get("market_trend_classification"),
        "current_3": {
            "sales": summary.get("current_3_sales"),
            "absorption_rate": summary.get("current_3_absorption_rate"),
            "active_listings": summary.get("current_3_active_listings"),
            "months_supply": summary.get("current_3_months_supply"),
            "median_close_price": summary.get("current_3_median_close_price"),
            "median_sales_dim": summary.get("current_3_median_sales_dim"),
        },
        "prior_4_6": {
            "sales": summary.get("prior_4_6_sales"),
            "absorption_rate": summary.get("prior_4_6_absorption_rate"),
            "active_listings": summary.get("prior_4_6_active_listings"),
            "months_supply": summary.get("prior_4_6_months_supply"),
            "median_close_price": summary.get("prior_4_6_median_close_price"),
            "median_sales_dim": summary.get("prior_4_6_median_sales_dim"),
        },
        "prior_7_12": {
            "sales": summary.get("prior_7_12_sales"),
            "absorption_rate": summary.get("prior_7_12_absorption_rate"),
            "active_listings": summary.get("prior_7_12_active_listings"),
            "months_supply": summary.get("prior_7_12_months_supply"),
            "median_close_price": summary.get("prior_7_12_median_close_price"),
            "median_sales_dim": summary.get("prior_7_12_median_sales_dim"),
        },
        "validation": summary.get("validation"),
    }


# ---------------------------------------------------------------------
# Output records
# ---------------------------------------------------------------------

def _build_adjusted_comp_records(comp_df: pd.DataFrame) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    for _idx, row in comp_df.iterrows():
        record = {
            "address": row.get("_address"),
            "status": row.get("_status_text"),
            "close_price": _round_money(row.get("_close_price")),
            "concessions": _round_money(row.get("_concessions")),
            "net_price": _round_money(row.get("_net_price")),
            "list_price": _round_money(row.get("_list_price")),
            "original_list_price": _round_money(row.get("_original_list_price")),
            "above_grade_sqft": _round_number(row.get("_above_grade_sqft")),
            "living_area": _round_number(row.get("_living_area")),
            "building_area_total": _round_number(row.get("_building_area_total")),
            "basement_sqft": _round_number(row.get("_basement_sqft")),
            "finished_basement_sqft": _round_number(row.get("_finished_basement_sqft")),
            "unfinished_basement_sqft": _round_number(row.get("_unfinished_basement_sqft")),
            "above_grade_adjustment": _round_money(row.get("_above_grade_adjustment")),
            "finished_basement_adjustment": _round_money(row.get("_finished_basement_adjustment")),
            "unfinished_basement_adjustment": _round_money(row.get("_unfinished_basement_adjustment")),
            "time_adjustment": _round_money(row.get("_time_adjustment")),
            "total_adjustments": _round_money(row.get("_total_adjustments")),
            "total_adjusted_price": _round_money(row.get("_adjusted_price")),
            "comp_score": _round_number(row.get("_comp_score"), decimals=2),
            "score_notes": row.get("_comp_score_notes"),
            "within_85_to_110_size_window": bool(row.get("_within_size_window")),
            "level_style_match": bool(row.get("_level_match")),
            "close_date": _json_safe(row.get("_close_date")),
            "days_in_mls": _round_number(row.get("_days_in_mls")),
            "year_built": _round_number(row.get("_year_built")),
            "property_subtype": row.get("_property_subtype"),
            "levels": row.get("_levels"),
            "subdivision": row.get("_subdivision"),
            "association_name": row.get("_association_name"),
            "association_name_2": row.get("_association_name_2"),
            "association_fee_total_annual": _round_money(row.get("_association_fee_total_annual")),
            "public_remarks_for_gpt_review": row.get("_public_remarks"),
            "broker_remarks_for_gpt_review": row.get("_broker_remarks"),
        }

        records.append(_json_safe(record))

    return records


# ---------------------------------------------------------------------
# Adjustment helpers
# ---------------------------------------------------------------------

def _sf_adjustment(subject_value: Any, comp_value: Any, rate: float) -> float:
    subject_num = _to_number(subject_value)
    comp_num = _to_number(comp_value)

    if subject_num is None or comp_num is None:
        return 0.0

    return float((subject_num - comp_num) * rate)


def _derive_unfinished_basement(
    total_basement: Any,
    finished_basement: Any,
    supplied_unfinished: Any,
) -> Optional[float]:
    supplied = _to_number(supplied_unfinished)

    if supplied is not None:
        return supplied

    total = _to_number(total_basement)
    finished = _to_number(finished_basement)

    if total is not None and finished is not None:
        return max(total - finished, 0)

    if total is not None and finished is None:
        return total

    return None


def _calculate_time_adjustment(
    net_price: float,
    close_date: Any,
    effective_date: Optional[pd.Timestamp],
    monthly_market_change_percent: float,
) -> float:
    if net_price <= 0:
        return 0.0

    if close_date is None or pd.isna(close_date) or effective_date is None:
        return 0.0

    months = _months_between(close_date, effective_date)

    if months <= 0:
        return 0.0

    months = min(months, 12)

    monthly_rate = monthly_market_change_percent / 100
    adjustment = net_price * monthly_rate * months

    max_adjustment = net_price * 0.08
    adjustment = max(-max_adjustment, min(max_adjustment, adjustment))

    return float(adjustment)


def _determine_effective_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if "_close_date" not in df.columns:
        return None

    dates = pd.to_datetime(df["_close_date"], errors="coerce").dropna()

    if dates.empty:
        return None

    return dates.max()


def _tokenize_address(value: Any) -> List[str]:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return [token for token in text.split() if token]


def _address_tokens_match(subject_address: Any, row_address: Any) -> bool:
    subject_tokens = _tokenize_address(subject_address)
    row_tokens = _tokenize_address(row_address)

    if not subject_tokens or not row_tokens:
        return False

    # Require street number when available, plus at least one non-directional street token.
    if subject_tokens[0].isdigit() and subject_tokens[0] not in row_tokens:
        return False

    ignored = {
        "e", "w", "n", "s", "east", "west", "north", "south",
        "pl", "place", "st", "street", "ave", "avenue", "dr", "drive",
        "ct", "court", "ln", "lane", "way", "rd", "road",
    }
    meaningful_subject = [token for token in subject_tokens[1:] if token not in ignored]
    hits = sum(1 for token in meaningful_subject if token in row_tokens)

    return hits >= 1


def _detect_subject_market_snapshot(subject: Dict[str, Any], all_prepared_df: pd.DataFrame) -> Dict[str, Any]:
    subject_address = subject.get("subject_address") or subject.get("address")
    snapshot = {
        "matched_in_market_file": False,
        "status": subject.get("status") or subject.get("mls_status"),
        "current_price": None,
        "original_price": None,
        "previous_price": None,
        "days_in_mls": None,
        "matched_address": None,
        "price_reduction_detected": False,
    }

    if all_prepared_df is None or all_prepared_df.empty or not subject_address:
        return snapshot

    for _idx, row in all_prepared_df.iterrows():
        row_address = row.get("_address")
        if not _address_tokens_match(subject_address, row_address):
            continue

        current_price = _round_money(row.get("_list_price"))
        original_price = _round_money(row.get("_original_list_price"))
        previous_price = _round_money(row.get("_previous_list_price"))
        status = str(row.get("_status_text") or "").strip().lower() or None

        snapshot.update(
            {
                "matched_in_market_file": True,
                "status": status,
                "current_price": current_price,
                "original_price": original_price,
                "previous_price": previous_price,
                "days_in_mls": _round_number(row.get("_days_in_mls")),
                "matched_address": row_address,
                "price_reduction_detected": bool(original_price and current_price and current_price < original_price),
            }
        )
        return snapshot

    return snapshot


# ---------------------------------------------------------------------
# Generic utilities
# ---------------------------------------------------------------------

def _row_address(row: pd.Series, column_map: Dict[str, Optional[str]]) -> Optional[str]:
    address_col = column_map.get("address")

    if address_col and pd.notna(row.get(address_col)):
        return str(row.get(address_col))

    street_number_col = column_map.get("street_number")
    street_name_col = column_map.get("street_name")
    city_col = column_map.get("city")

    parts = []

    for col in [street_number_col, street_name_col, city_col]:
        if col and pd.notna(row.get(col)):
            parts.append(str(row.get(col)))

    return " ".join(parts).strip() or None


def _normalize_column_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _clean_text(value: Any) -> str:
    if value is None or _is_missing(value):
        return ""

    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _normalize_level(value: Any) -> str:
    text = _clean_text(value)

    if text in {"", "blank", "none", "nan"}:
        return ""

    if text in {"one", "1", "1story", "onestory", "ranch", "ranchstyle"}:
        return "one"

    if text in {"two", "2", "2story", "twostory"}:
        return "two"

    if text in {"bilevel", "bi"}:
        return "bilevel"

    if text in {"trilevel", "tri"}:
        return "trilevel"

    if text in {"multisplit", "split", "splitlevel", "multilevel", "multi"}:
        return "multisplit"

    if text in {"threeormore", "three", "3", "3ormore", "threeplus"}:
        return "threeormore"

    return text


def _levels_match(subject_level: str, comp_levels_value: Any) -> bool:
    comp_level = _normalize_level(comp_levels_value)

    if not subject_level or not comp_level:
        return False

    return subject_level == comp_level


def _normalize_property_subtype(value: Any) -> str:
    text = _clean_text(value)

    if text in {
        "sfr",
        "sf",
        "singlefamily",
        "singlefamilyresidence",
        "detached",
        "residentialdetached",
    }:
        return "singlefamilyresidence"

    return text


def _first_number(data: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in data:
            number = _to_number(data.get(key))
            if number is not None:
                return number

    return None


def _to_number(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None

    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    cleaned = str(value)
    cleaned = cleaned.replace("$", "")
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("%", "")
    cleaned = cleaned.strip()

    if cleaned in {"", "-", "None", "nan", "NaN", "NULL"}:
        return None

    try:
        return float(cleaned)
    except Exception:
        return None


def _to_datetime(value: Any) -> Optional[pd.Timestamp]:
    if _is_missing(value):
        return None

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed
    except Exception:
        return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    return False


def _clean_numeric_list(values: List[Any]) -> List[float]:
    output = []

    for value in values:
        number = _to_number(value)
        if number is not None and number > 0:
            output.append(float(number))

    return output


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None

    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2

    if n % 2 == 1:
        return sorted_values[mid]

    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def _average(values: List[float]) -> Optional[float]:
    if not values:
        return None

    return sum(values) / len(values)


def _weighted_average(values: List[float], weights: List[float]) -> Optional[float]:
    if not values or not weights or len(values) != len(weights):
        return None

    total_weight = sum(weights)

    if total_weight <= 0:
        return None

    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _round_money(value: Any) -> Optional[int]:
    number = _to_number(value)

    if number is None:
        return None

    return int(round(number))


def _round_number(value: Any, decimals: int = 0) -> Optional[float]:
    number = _to_number(value)

    if number is None:
        return None

    return round(number, decimals)


def _safe_pct_diff(value: Any, anchor: Any) -> Optional[float]:
    value_num = _to_number(value)
    anchor_num = _to_number(anchor)

    if value_num is None or anchor_num is None or anchor_num == 0:
        return None

    return abs(value_num - anchor_num) / anchor_num


def _months_between(start_date: Any, end_date: Any) -> float:
    start = _to_datetime(start_date)
    end = _to_datetime(end_date)

    if start is None or end is None:
        return 0.0

    days = (end - start).days

    return max(0.0, days / 30.4375)


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")

    if isinstance(value, pd.Series):
        return value.to_dict()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if _is_missing(value):
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value
