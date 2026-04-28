from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

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


def _facts_to_subject_profile(
    facts: Dict[str, Any],
    fallback_address: str = "",
) -> Dict[str, Any]:
    """
    Convert Realist parser output into the ICHIBAN subject profile structure.

    The Realist parser returns source-specific fields.
    The valuation engine needs normalized internal fields.
    """

    profile = blank_subject_profile(
        facts.get("full_address") or fallback_address or ""
    )

    field_sources: Dict[str, str] = {}

    def set_field(profile_key: str, value: Any, source: str = "Realist PDF") -> None:
        if value not in (None, "", 0):
            profile[profile_key] = value
            field_sources[profile_key] = source

    set_field("subject_address", facts.get("full_address"))
    set_field("county", facts.get("county"))
    set_field("apn", facts.get("apn"))
    set_field("clip", facts.get("clip"))
    set_field("schedule_number", facts.get("schedule_number"))

    # IMPORTANT:
    # In the Realist PDF, "Bldg Sq Ft" is being treated as the subject's
    # above-grade/building square footage for comp-sizing intake.
    set_field("above_grade_sqft", facts.get("building_sqft"))

    set_field("lot_sqft", facts.get("lot_sqft"))
    set_field("year_built", facts.get("year_built"))

    # Realist Type SFR should satisfy the internal property type for now.
    set_field("property_type", facts.get("property_type"))
    set_field("property_subtype", facts.get("property_type"))

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

    # Extra fields from Realist that may not be in the original requirements list.
    extra_fields = [
        "county",
        "apn",
        "clip",
        "schedule_number",
        "lot_sqft",
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
                profile.get(field),
                profile.get("field_sources", {}).get(field, ""),
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

        if diagnostic.recommended_parser == "realist_pdf_coordinate_parser":
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
        "Above Grade / Building SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("above_grade_sqft")),
        help="This is the critical comp-sizing field.",
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

    basement_sqft = st.number_input(
        "Basement SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("basement_sqft")),
    )

    finished_basement_sqft = st.number_input(
        "Finished Basement SqFt",
        min_value=0,
        step=1,
        value=_safe_int(profile.get("finished_basement_sqft")),
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
    zoning = st.text_input("Zoning", value=_safe_text(profile.get("zoning")))


# ---------------------------------------------------------------------
# Save verified subject
# ---------------------------------------------------------------------

if st.button("Save Verified Subject", type="primary"):
    manual_patch = {
        "subject_address": subject_address.strip() or None,
        "above_grade_sqft": None if above_grade_sqft == 0 else above_grade_sqft,
        "property_type": property_type.strip() or None,
        "property_subtype": property_subtype.strip() or None,
        "year_built": None if year_built == 0 else year_built,
        "lot_sqft": None if lot_sqft == 0 else lot_sqft,
        "basement_sqft": None if basement_sqft == 0 else basement_sqft,
        "finished_basement_sqft": None if finished_basement_sqft == 0 else finished_basement_sqft,
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