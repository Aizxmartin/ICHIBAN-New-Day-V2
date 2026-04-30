from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.address_subject_profile import blank_subject_profile
from core.pdf_diagnostics import probe_document_source
from core.subject_acquisition import (
    clear_verified_subject,
    load_verified_subject,
    parse_realist_subject,
    save_verified_subject,
    subject_is_verified,
)
from core.subject_acquisition.validate_subject_profile import validate_subject_profile
from core.subject_requirements import (
    FIELD_LABELS,
    OPTIONAL_SUBJECT_FIELDS,
    REQUIRED_SUBJECT_FIELDS,
)


st.set_page_config(
    page_title="ICHIBAN - Subject Verification",
    page_icon="🏡",
    layout="wide",
)

st.title("Module 2 — Subject Verification")
st.subheader("Diagnose, extract, verify, and lock the subject property before valuation")


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

LEVEL_OPTIONS = [
    "",
    "Bi-Level",
    "Multi/Split",
    "One",
    "Three Or More",
    "Tri-Level",
    "Two",
]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def _safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", ""))
    except Exception:
        return 0.0


def _positive_number(value: Any) -> float | None:
    """
    Convert a value to a positive number or None.
    Used for Realist square-footage reconciliation.
    """

    try:
        if value in (None, ""):
            return None
        number = float(str(value).replace(",", ""))
        if number <= 0:
            return None
        return number
    except Exception:
        return None


def _rounded_int(value: Any) -> int | None:
    number = _positive_number(value)
    if number is None:
        return None
    return int(round(number))


def _option_index(options: List[str], value: Any) -> int:
    """
    Return the index for a Streamlit selectbox option.
    Blank/unknown values default to the first option.
    """

    value_text = _safe_text(value).strip().lower()

    for idx, option in enumerate(options):
        if option.strip().lower() == value_text:
            return idx

    return 0


def _infer_levels_from_realist(facts: Dict[str, Any]) -> str | None:
    """
    Convert common Realist style/story language into the MLS-compatible Levels value.
    This is intentionally conservative; the user can correct it on the verification screen.
    """

    raw_values = [
        facts.get("levels"),
        facts.get("Levels"),
        facts.get("stories"),
        facts.get("Stories"),
        facts.get("style"),
        facts.get("Style"),
        facts.get("land_use_corelogic"),
    ]

    text = " ".join(str(v) for v in raw_values if v not in (None, "")).lower()

    if not text:
        return None

    if "ranch" in text or "1 story" in text or "one story" in text or text.strip() == "1":
        return "One"

    if "two" in text or "2 story" in text or "2-story" in text:
        return "Two"

    if "tri" in text:
        return "Tri-Level"

    if "bi" in text:
        return "Bi-Level"

    if "split" in text or "multi" in text:
        return "Multi/Split"

    return None


def _facts_to_subject_profile(
    facts: Dict[str, Any],
    fallback_address: str = "",
) -> Dict[str, Any]:
    """
    Convert Realist parser output into the ICHIBAN subject profile structure.

    The Realist parser returns source-specific fields.
    The valuation engine needs normalized internal fields.

    Critical square-footage rule:
    - Realist top summary "Bldg Sq Ft" can include finished basement.
    - It must not be used as MLS-style Above Grade Finished Area when the
      detailed "Bldg Sq Ft - Above Ground" field is available.
    """

    profile = blank_subject_profile(
        facts.get("full_address") or fallback_address or ""
    )

    field_sources: Dict[str, str] = {}
    verification_notes: List[str] = list(facts.get("data_verification_notes") or [])

    def set_field(profile_key: str, value: Any, source: str = "Realist PDF") -> None:
        if value not in (None, "", 0, 0.0):
            profile[profile_key] = value
            field_sources[profile_key] = source

    set_field("subject_address", facts.get("full_address"))
    set_field("county", facts.get("county"))
    set_field("apn", facts.get("apn"))
    set_field("clip", facts.get("clip"))
    set_field("schedule_number", facts.get("schedule_number"))

    # -----------------------------------------------------------------
    # Realist square-footage reconciliation
    # -----------------------------------------------------------------
    #
    # These are the fields produced by core/subject_acquisition/
    # realist_pdf_coordinate_parser.py:
    #
    # building_sqft                  = top summary "Bldg Sq Ft"
    # building_sqft_above_ground     = "Bldg Sq Ft - Above Ground"
    # basement_sqft                  = "Bldg Sq Ft - Basement"
    # finished_basement_sqft         = "Bldg Sq Ft - Finished Basement"
    # unfinished_basement_sqft       = "Bldg Sq Ft - Unfinished Basement"
    # total_building_sqft            = "Bldg Sq Ft - Total"
    # finished_building_sqft         = "Bldg Sq Ft - Finished"
    #
    # For Boca:
    # building_sqft / finished_building_sqft = 2653
    # building_sqft_above_ground = 2065
    # finished_basement_sqft = 588
    # basement_sqft = 1152
    # unfinished_basement_sqft = 564
    # total_building_sqft = 3217

    direct_above_grade = _rounded_int(facts.get("building_sqft_above_ground"))

    total_finished_sqft = _rounded_int(
        facts.get("finished_building_sqft")
        or facts.get("building_sqft")
    )

    summary_building_sqft = _rounded_int(facts.get("building_sqft"))
    basement_sqft = _rounded_int(facts.get("basement_sqft"))
    finished_basement_sqft = _rounded_int(facts.get("finished_basement_sqft"))
    unfinished_basement_sqft = _rounded_int(facts.get("unfinished_basement_sqft"))
    building_area_total = _rounded_int(facts.get("total_building_sqft"))

    if unfinished_basement_sqft is None and basement_sqft is not None and finished_basement_sqft is not None:
        inferred_unfinished = basement_sqft - finished_basement_sqft
        if inferred_unfinished >= 0:
            unfinished_basement_sqft = inferred_unfinished
            verification_notes.append(
                f"Unfinished Basement SqFt was inferred from Total Basement SqFt ({basement_sqft}) "
                f"minus Finished Basement SqFt ({finished_basement_sqft}) = {inferred_unfinished}."
            )

    if direct_above_grade is not None:
        set_field("above_grade_sqft", direct_above_grade, "Realist PDF: Bldg Sq Ft - Above Ground")
        set_field("above_grade_source", "Bldg Sq Ft - Above Ground", "Realist PDF")

        if total_finished_sqft is not None and finished_basement_sqft is not None:
            expected_total_finished = direct_above_grade + finished_basement_sqft
            if expected_total_finished == total_finished_sqft:
                verification_notes.append(
                    f"Square footage cross-check passed: Above Ground SqFt ({direct_above_grade}) "
                    f"+ Finished Basement SqFt ({finished_basement_sqft}) = Total Finished SqFt ({total_finished_sqft})."
                )
            else:
                verification_notes.append(
                    f"Square footage cross-check needs review: Above Ground SqFt ({direct_above_grade}) "
                    f"+ Finished Basement SqFt ({finished_basement_sqft}) = {expected_total_finished}, "
                    f"but Total Finished SqFt shows {total_finished_sqft}."
                )

    elif total_finished_sqft is not None and finished_basement_sqft is not None:
        inferred_above_grade = total_finished_sqft - finished_basement_sqft
        if inferred_above_grade > 0:
            set_field(
                "above_grade_sqft",
                inferred_above_grade,
                "Inferred: Total Finished SqFt minus Finished Basement SqFt",
            )
            set_field(
                "above_grade_source",
                "Inferred from total finished sqft minus finished basement sqft",
                "Realist PDF",
            )
            verification_notes.append(
                f"Above Grade Finished Area was inferred because Bldg Sq Ft - Above Ground was missing. "
                f"Calculation: Total Finished SqFt ({total_finished_sqft}) minus Finished Basement SqFt "
                f"({finished_basement_sqft}) = {inferred_above_grade}. Manual verification recommended."
            )

    else:
        # Last resort only. This keeps the workflow alive but clearly flags the risk.
        set_field("above_grade_sqft", summary_building_sqft, "Fallback: Realist summary Bldg Sq Ft")
        set_field("above_grade_source", "Fallback: Realist summary Bldg Sq Ft", "Realist PDF")
        if summary_building_sqft is not None:
            verification_notes.append(
                "Above Grade Finished Area used the Realist top summary Bldg Sq Ft as a fallback. "
                "This may include finished basement area. Manual verification required before valuation."
            )

    set_field("summary_building_sqft", summary_building_sqft, "Realist PDF: top summary Bldg Sq Ft")
    set_field("total_finished_sqft", total_finished_sqft, "Realist PDF: Bldg Sq Ft - Finished / summary")
    set_field("building_area_total", building_area_total, "Realist PDF: Bldg Sq Ft - Total")
    set_field("basement_sqft", basement_sqft, "Realist PDF: Bldg Sq Ft - Basement")
    set_field("finished_basement_sqft", finished_basement_sqft, "Realist PDF: Bldg Sq Ft - Finished Basement")
    set_field("unfinished_basement_sqft", unfinished_basement_sqft, "Realist PDF: Bldg Sq Ft - Unfinished Basement")

    set_field("lot_sqft", facts.get("lot_sqft"))
    set_field("year_built", facts.get("year_built"))

    # -----------------------------------------------------------------
    # Beds / Baths
    # -----------------------------------------------------------------
    # Realist may show beds/baths in two places:
    # - Page 1 summary row: Beds, Full Baths, Half Baths
    # - Characteristics: Bedrooms, Baths - Total
    #
    # The parser normalizes those into:
    # - beds
    # - full_baths
    # - half_baths
    # - total_baths
    #
    # The user can still manually correct these before saving the verified subject.

    set_field("beds", facts.get("beds"), "Realist PDF: Beds / Bedrooms")

    total_baths = facts.get("total_baths")

    if total_baths is None:
        full_baths = facts.get("full_baths")
        half_baths = facts.get("half_baths") or 0

        if full_baths is not None:
            total_baths = float(full_baths) + (float(half_baths) * 0.5)

    set_field("baths", total_baths, "Realist PDF: Baths - Total / Full + Half Baths")

    set_field("property_type", facts.get("property_type"))
    set_field("property_subtype", facts.get("property_type"))

    inferred_levels = _infer_levels_from_realist(facts)
    set_field("levels", inferred_levels, "Realist PDF style/stories interpretation")

    set_field(
        "subject_layout_notes",
        facts.get("subject_layout_notes")
        or facts.get("layout_notes")
        or facts.get("style_notes")
        or facts.get("land_use_corelogic"),
    )

    set_field("neighborhood_name", facts.get("neighborhood_name"))
    set_field("neighborhood_code", facts.get("neighborhood_code"))
    set_field("subdivision", facts.get("subdivision"))
    set_field("zoning", facts.get("zoning"))

    set_field("school_district", facts.get("school_district"))
    set_field("elementary_school", facts.get("elementary_school"))
    set_field("middle_school", facts.get("middle_school"))
    set_field("high_school", facts.get("high_school"))

    set_field("real_avm", facts.get("real_avm"))
    set_field("real_avm_range_low", facts.get("real_avm_low"))
    set_field("real_avm_range_high", facts.get("real_avm_high"))

    profile["field_sources"] = {
        **profile.get("field_sources", {}),
        **field_sources,
    }

    profile["subject_acquisition_status"] = "parsed_from_realist_pdf"
    profile["parser_confidence"] = facts.get("confidence")
    profile["parser_warnings"] = facts.get("warnings", [])
    profile["raw_pdf_text_excerpt"] = facts.get("raw_text_sample", "")
    profile["data_verification_notes"] = verification_notes

    return validate_subject_profile(profile)


def _apply_manual_patch(profile: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply user-corrected values from the editable verification screen.
    """

    field_sources = dict(profile.get("field_sources", {}))

    for key, value in patch.items():
        if value not in (None, "", 0, 0.0):
            profile[key] = value
            field_sources[key] = "User verified / manual correction"

    profile["field_sources"] = field_sources
    profile["subject_acquisition_status"] = "user_verified"
    return validate_subject_profile(profile)


def _show_profile_table(profile: Dict[str, Any]) -> None:
    """
    Display the current working profile in a readable table.
    """

    display_fields = []

    seen = set()
    for field in REQUIRED_SUBJECT_FIELDS + OPTIONAL_SUBJECT_FIELDS:
        if field not in seen:
            display_fields.append(field)
            seen.add(field)

    extra_fields = [
        "county",
        "apn",
        "clip",
        "schedule_number",
        "summary_building_sqft",
        "total_finished_sqft",
        "building_area_total",
        "above_grade_source",
        "lot_sqft",
        "levels",
        "subject_layout_notes",
        "unfinished_basement_sqft",
        "neighborhood_name",
        "neighborhood_code",
        "subdivision",
        "zoning",
        "school_district",
        "elementary_school",
        "middle_school",
        "high_school",
        "parser_confidence",
    ]

    for field in extra_fields:
        if field not in seen:
            display_fields.append(field)
            seen.add(field)

    rows = []
    for field in display_fields:
        rows.append(
            [
                FIELD_LABELS.get(field, field),
                _safe_text(profile.get(field)),
                _safe_text(profile.get("field_sources", {}).get(field, "")),
            ]
        )

    df = pd.DataFrame(rows, columns=["Field", "Current Value", "Source"])
    st.dataframe(df, width="stretch", hide_index=True)


# ---------------------------------------------------------------------
# Load current profile state
# ---------------------------------------------------------------------

verified_subject = load_verified_subject()

if verified_subject:
    profile = verified_subject
    st.session_state["subject_profile"] = profile
    st.session_state["subject_ready"] = True
else:
    profile = st.session_state.get("subject_profile")

    if not profile:
        address = st.session_state.get("subject_address", "")
        profile = blank_subject_profile(address)

    profile = validate_subject_profile(profile)
    st.session_state["subject_profile"] = profile


# ---------------------------------------------------------------------
# Page explanation
# ---------------------------------------------------------------------

st.markdown(
    """
### Hard Gate

ICHIBAN must lock the subject property before valuation starts.

This page now works in this order:

1. Upload the subject property PDF.
2. Diagnose the file before extraction.
3. Route readable Realist/CoreLogic PDFs to the Realist parser.
4. Show extracted facts in editable fields.
5. Save verified subject data.
6. Do not allow valuation until the subject is verified.

**Important square footage rule:** Above-grade finished area must remain separate from basement area.  
Basement area is adjusted separately in valuation.
"""
)


# ---------------------------------------------------------------------
# Upload + diagnostic + parser
# ---------------------------------------------------------------------

with st.container(border=True):
    st.markdown("#### Subject PDF Diagnostic + Parser")

    uploaded_pdf = st.file_uploader(
        "Upload the subject property PDF",
        type=["pdf"],
        help=(
            "Upload the Realist/CoreLogic subject property PDF. "
            "ICHIBAN will diagnose the file first, then route it to the correct parser."
        ),
    )

    col_run, col_clear = st.columns([1, 1])

    with col_run:
        run_parser = st.button("Run Subject PDF Diagnostic + Parser", type="primary")

    with col_clear:
        clear_subject = st.button("Clear Verified Subject / Start Over")

    if clear_subject:
        clear_verified_subject()
        st.session_state.pop("subject_profile", None)
        st.session_state["subject_ready"] = False
        st.success("Verified subject data cleared. You can upload a new subject file.")
        st.rerun()

    if run_parser:
        if uploaded_pdf is None:
            st.error("Please upload a subject PDF first.")
            st.stop()

        suffix = Path(uploaded_pdf.name).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_pdf.getbuffer())
            temp_path = tmp.name

        diagnostic = probe_document_source(temp_path)
        diagnostic_dict = diagnostic.to_dict()

        profile["pdf_diagnostic"] = diagnostic_dict
        profile["pdf_extraction_diagnostics"] = [
            f"File type: {diagnostic.file_type}",
            f"Likely source: {diagnostic.likely_source}",
            f"Category: {diagnostic.document_category}",
            f"Recommended parser: {diagnostic.recommended_parser}",
            f"Manual fallback required: {diagnostic.manual_fallback_required}",
            f"Text found: {diagnostic.text_found}",
            f"Coordinate text available: {diagnostic.coordinate_text_available}",
            f"Image only: {diagnostic.image_only}",
        ]

        should_run_realist_parser = (
            diagnostic.recommended_parser == "realist_pdf_coordinate_parser"
            or (
                diagnostic.likely_source == "realist_corelogic"
                and diagnostic.coordinate_text_available
            )
        )

        if should_run_realist_parser:
            facts = parse_realist_subject(temp_path)
            facts_dict = facts.to_dict()

            parsed_profile = _facts_to_subject_profile(
                facts_dict,
                fallback_address=st.session_state.get("subject_address", ""),
            )

            parsed_profile["pdf_diagnostic"] = diagnostic_dict
            parsed_profile["pdf_extraction_diagnostics"] = profile["pdf_extraction_diagnostics"]

            st.session_state["subject_profile"] = parsed_profile
            profile = parsed_profile

            if profile.get("subject_profile_ready"):
                st.success(
                    "Subject facts extracted successfully. Please review and save the verified subject below."
                )
            else:
                missing_labels = ", ".join(
                    FIELD_LABELS.get(f, f)
                    for f in profile.get("missing_required_fields", [])
                )
                st.warning(
                    f"Subject extraction worked, but required fields are still missing: {missing_labels}"
                )
        else:
            st.session_state["subject_profile"] = profile
            st.warning(
                "This PDF was diagnosed, but it is not currently routed to the Realist parser. "
                "Use the manual verification fields below."
            )


# ---------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------

left, right = st.columns([1.25, 1])

with left:
    st.markdown("#### Current Subject Profile")
    _show_profile_table(profile)

    status = profile.get("subject_acquisition_status", "not_started")
    st.caption(f"Acquisition status: {status}")

    if subject_is_verified():
        st.success("Verified subject file exists: data/verified_subject.json")
    else:
        st.warning("Subject has not been saved as verified yet.")

    with st.expander("PDF extraction diagnostics", expanded=False):
        diagnostics = profile.get("pdf_extraction_diagnostics", []) or []

        if diagnostics:
            for item in diagnostics:
                st.write(f"- {item}")
        else:
            st.caption("No PDF diagnostics are available yet.")

        raw_excerpt = profile.get("raw_pdf_text_excerpt") or ""
        if raw_excerpt:
            st.text_area("Raw extracted text excerpt", raw_excerpt, height=240)

        pdf_diagnostic = profile.get("pdf_diagnostic")
        if pdf_diagnostic:
            st.json(pdf_diagnostic)

    with st.expander("Subject data verification notes", expanded=False):
        notes = profile.get("data_verification_notes", []) or []
        if notes:
            for note in notes:
                st.write(f"- {note}")
        else:
            st.caption("No verification notes are available yet.")


with right:
    st.markdown("#### Verify / Correct Subject Facts")
    st.write(
        "Review these fields. Correct anything that is missing or wrong, then save the verified subject."
    )

    subject_address = st.text_input(
        "Subject Address",
        value=_safe_text(profile.get("subject_address")),
    )

    above_grade_sqft = st.number_input(
        "Above Grade Finished Area",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("above_grade_sqft")),
        help=(
            "Use the subject's above-grade finished area only. "
            "Do not include finished basement area here."
        ),
    )

    property_type = st.text_input(
        "Property Type",
        value=_safe_text(profile.get("property_type")),
        help="Examples: SFR, Single Family Residence, Condominium, Townhouse",
    )

    property_subtype = st.text_input(
        "Property Subtype",
        value=_safe_text(profile.get("property_subtype")),
    )

    levels = st.selectbox(
        "Levels",
        options=LEVEL_OPTIONS,
        index=_option_index(
            LEVEL_OPTIONS,
            profile.get("levels") or profile.get("Levels"),
        ),
        help=(
            "Select the MLS-compatible Levels value. Use One for ranch / one-story homes, "
            "including ranch homes with walkout basements."
        ),
    )

    subject_layout_notes = st.text_input(
        "Subject Layout Notes",
        value=_safe_text(profile.get("subject_layout_notes")),
        help="Example: 1-story ranch with walkout basement.",
    )

    year_built = st.number_input(
        "Year Built",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("year_built")),
    )

    lot_sqft = st.number_input(
        "Lot SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("lot_sqft")),
    )

    total_finished_sqft = st.number_input(
        "Total Finished SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("total_finished_sqft")),
        help=(
            "Realist may show this as Bldg Sq Ft or Bldg Sq Ft - Finished. "
            "This can include finished basement and should not be used for comp-size filtering."
        ),
    )

    building_area_total = st.number_input(
        "Building Total SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("building_area_total")),
        help="Realist Bldg Sq Ft - Total, typically above ground plus total basement.",
    )

    basement_sqft = st.number_input(
        "Total Basement SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("basement_sqft")),
        help="Total basement square footage, including finished and unfinished basement area.",
    )

    finished_basement_sqft = st.number_input(
        "Finished Basement SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("finished_basement_sqft")),
    )

    unfinished_basement_sqft = st.number_input(
        "Unfinished Basement SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("unfinished_basement_sqft")),
        help=(
            "If left blank but total basement and finished basement are entered, "
            "the valuation engine can derive this number."
        ),
    )

    beds = st.number_input(
        "Bedrooms",
        min_value=0.0,
        step=1.0,
        value=_safe_float(profile.get("beds")),
    )

    baths = st.number_input(
        "Bathrooms",
        min_value=0.0,
        step=0.5,
        value=_safe_float(profile.get("baths")),
    )

    st.markdown("##### AVM / Online Estimate Support")

    real_avm = st.number_input(
        "RealAVM",
        min_value=0,
        step=1000,
        value=_safe_int(profile.get("real_avm")),
    )

    real_avm_low = st.number_input(
        "RealAVM Range Low",
        min_value=0,
        step=1000,
        value=_safe_int(profile.get("real_avm_range_low")),
    )

    real_avm_high = st.number_input(
        "RealAVM Range High",
        min_value=0,
        step=1000,
        value=_safe_int(profile.get("real_avm_range_high")),
    )

    zillow_estimate = st.number_input(
        "Zillow Estimate / Zestimate",
        min_value=0,
        step=1000,
        value=_safe_int(profile.get("zillow_estimate")),
    )

    redfin_estimate = st.number_input(
        "Redfin Estimate",
        min_value=0,
        step=1000,
        value=_safe_int(profile.get("redfin_estimate")),
    )

    st.markdown("##### Public Record / Location Support")

    apn = st.text_input("APN", value=_safe_text(profile.get("apn")))

    schedule_number = st.text_input(
        "Schedule Number",
        value=_safe_text(profile.get("schedule_number")),
    )

    neighborhood_name = st.text_input(
        "Neighborhood",
        value=_safe_text(profile.get("neighborhood_name")),
    )

    subdivision = st.text_input(
        "Subdivision",
        value=_safe_text(profile.get("subdivision")),
    )

    zoning = st.text_input(
        "Zoning",
        value=_safe_text(profile.get("zoning")),
    )


# ---------------------------------------------------------------------
# Save verified subject
# ---------------------------------------------------------------------

if st.button("Save Verified Subject", type="primary"):
    manual_patch = {
        "subject_address": subject_address.strip() or None,
        "above_grade_sqft": None if above_grade_sqft == 0 else above_grade_sqft,
        "property_type": property_type.strip() or None,
        "property_subtype": property_subtype.strip() or None,
        "levels": levels.strip() or None,
        "subject_layout_notes": subject_layout_notes.strip() or None,
        "year_built": None if year_built == 0 else year_built,
        "lot_sqft": None if lot_sqft == 0 else lot_sqft,
        "total_finished_sqft": None if total_finished_sqft == 0 else total_finished_sqft,
        "building_area_total": None if building_area_total == 0 else building_area_total,
        "basement_sqft": None if basement_sqft == 0 else basement_sqft,
        "finished_basement_sqft": None if finished_basement_sqft == 0 else finished_basement_sqft,
        "unfinished_basement_sqft": None if unfinished_basement_sqft == 0 else unfinished_basement_sqft,
        "beds": None if beds == 0 else beds,
        "baths": None if baths == 0 else baths,
        "real_avm": None if real_avm == 0 else real_avm,
        "real_avm_range_low": None if real_avm_low == 0 else real_avm_low,
        "real_avm_range_high": None if real_avm_high == 0 else real_avm_high,
        "zillow_estimate": None if zillow_estimate == 0 else zillow_estimate,
        "redfin_estimate": None if redfin_estimate == 0 else redfin_estimate,
        "apn": apn.strip() or None,
        "schedule_number": schedule_number.strip() or None,
        "neighborhood_name": neighborhood_name.strip() or None,
        "subdivision": subdivision.strip() or None,
        "zoning": zoning.strip() or None,
    }

    verified_profile = _apply_manual_patch(profile, manual_patch)

    if not verified_profile.get("subject_profile_ready"):
        missing_labels = ", ".join(
            FIELD_LABELS.get(f, f)
            for f in verified_profile.get("missing_required_fields", [])
        )
        st.error(
            f"Subject cannot be locked yet. Missing required fields: {missing_labels}"
        )
    else:
        save_path = save_verified_subject(verified_profile)
        st.session_state["subject_profile"] = verified_profile
        st.session_state["subject_ready"] = True
        st.success(f"Subject verified and saved to {save_path}")


# ---------------------------------------------------------------------
# Navigation / handoff
# ---------------------------------------------------------------------

st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button("Back to Address Intake"):
        st.switch_page("pages/1_address_intake.py")

with col2:
    if st.session_state.get("subject_ready") or subject_is_verified():
        st.success("Ready for Module 3 handoff.")
    else:
        st.warning("Subject is not locked yet. Do not proceed to valuation.")