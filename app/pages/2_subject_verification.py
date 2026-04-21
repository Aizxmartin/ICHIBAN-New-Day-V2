import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.address_subject_profile import blank_subject_profile
from core.subject_acquisition.acquire_subject_profile import acquire_subject_profile
from core.subject_acquisition.validate_subject_profile import validate_subject_profile
from core.subject_requirements import FIELD_LABELS, OPTIONAL_SUBJECT_FIELDS, REQUIRED_SUBJECT_FIELDS

st.set_page_config(page_title="ICHIBAN - Subject Verification", page_icon="🏡", layout="wide")

st.title("Module 2 — Subject Acquisition")
st.subheader("Secure the subject property before valuation begins")

profile = st.session_state.get("subject_profile")
if not profile:
    address = st.session_state.get("subject_address", "")
    if not address:
        st.error("No subject address was found in session. Please return to Module 1.")
        st.stop()
    profile = blank_subject_profile(address)

profile = validate_subject_profile(profile)
st.session_state["subject_profile"] = profile

st.markdown(
    """
### Hard Gate
ICHIBAN must secure the subject property before valuation starts.

This page now works in this order:
1. try the subject property PDF
2. keep any usable subject facts
3. ask only for the missing required fields

Valuation should not proceed until the required subject fields are locked.
"""
)

with st.container(border=True):
    st.markdown("#### Subject PDF Attempt")
    uploaded_pdf = st.file_uploader(
        "Upload the subject property PDF",
        type=["pdf"],
        help="Upload the Realist or subject property PDF so ICHIBAN can try to pull address, AG square footage, and property type.",
    )
    if st.button("Run Subject Acquisition", type="primary"):
        result = acquire_subject_profile(
            subject_pdf=uploaded_pdf,
            fallback_address=st.session_state.get("subject_address", ""),
        )
        st.session_state["subject_profile"] = result
        profile = result
        if profile.get("subject_profile_ready"):
            st.success("Subject profile locked. Required subject fields are in place.")
        else:
            missing_labels = ", ".join(FIELD_LABELS.get(f, f) for f in profile.get("missing_required_fields", []))
            st.warning(f"Subject profile is still blocked. Missing: {missing_labels}")

left, right = st.columns([1.2, 1])

with left:
    st.markdown("#### Current Locked / Working Subject Profile")
    rows = []
    for field in REQUIRED_SUBJECT_FIELDS + OPTIONAL_SUBJECT_FIELDS:
        rows.append(
            [
                FIELD_LABELS.get(field, field),
                profile.get(field),
                profile.get("field_sources", {}).get(field, ""),
            ]
        )
    df = pd.DataFrame(rows, columns=["Field", "Current Value", "Source"])
    st.dataframe(df, width="stretch", hide_index=True)

    status = profile.get("subject_acquisition_status", "not_started")
    st.caption(f"Acquisition status: {status}")


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

with right:
    st.markdown("#### Minimal Manual Recovery")
    st.write("Only fill what is still missing. This is the last resort, not the default intake.")

    subject_address = st.text_input(
        "Subject Address",
        value=profile.get("subject_address") or "",
        disabled=bool(profile.get("subject_address")),
    )
    above_grade_default = int(profile.get("above_grade_sqft") or 0)
    above_grade_sqft = st.number_input(
        "Above Grade SqFt",
        min_value=0,
        step=1,
        value=above_grade_default,
        help="This is the critical comp-sizing field.",
    )
    property_type = st.text_input(
        "Property Type",
        value=profile.get("property_type") or "",
        help="Examples: Single Family Residence, Condominium, Townhouse",
    )

    st.markdown("##### Optional support fields")
    property_subtype = st.text_input("Property Subtype", value=profile.get("property_subtype") or "")
    beds = st.number_input("Bedrooms", min_value=0.0, step=1.0, value=float(profile.get("beds") or 0.0))
    baths = st.number_input("Bathrooms", min_value=0.0, step=0.5, value=float(profile.get("baths") or 0.0))
    year_built = st.number_input("Year Built", min_value=0, step=1, value=int(profile.get("year_built") or 0))
    real_avm = st.number_input("RealAVM", min_value=0, step=1000, value=int(profile.get("real_avm") or 0))
    real_avm_low = st.number_input("RealAVM Range Low", min_value=0, step=1000, value=int(profile.get("real_avm_range_low") or 0))
    real_avm_high = st.number_input("RealAVM Range High", min_value=0, step=1000, value=int(profile.get("real_avm_range_high") or 0))
    basement_sqft = st.number_input("Basement SqFt", min_value=0, step=1, value=int(profile.get("basement_sqft") or 0))
    finished_basement_sqft = st.number_input(
        "Finished Basement SqFt", min_value=0, step=1, value=int(profile.get("finished_basement_sqft") or 0)
    )

if st.button("Apply Minimal Manual Recovery"):
    manual_patch = {
        "subject_address": subject_address.strip() or None,
        "above_grade_sqft": None if above_grade_sqft == 0 else above_grade_sqft,
        "property_type": property_type.strip() or None,
        "property_subtype": property_subtype.strip() or None,
        "beds": None if beds == 0 else beds,
        "baths": None if baths == 0 else baths,
        "year_built": None if year_built == 0 else year_built,
        "real_avm": None if real_avm == 0 else real_avm,
        "real_avm_range_low": None if real_avm_low == 0 else real_avm_low,
        "real_avm_range_high": None if real_avm_high == 0 else real_avm_high,
        "basement_sqft": None if basement_sqft == 0 else basement_sqft,
        "finished_basement_sqft": None if finished_basement_sqft == 0 else finished_basement_sqft,
    }
    result = acquire_subject_profile(
        fallback_address=st.session_state.get("subject_address", ""),
        manual_patch=manual_patch,
    )
    st.session_state["subject_profile"] = result
    profile = result

    if profile.get("subject_profile_ready"):
        st.success("Subject profile locked after manual recovery.")
    else:
        missing_labels = ", ".join(FIELD_LABELS.get(f, f) for f in profile.get("missing_required_fields", []))
        st.error(f"Subject profile is still blocked. Missing required fields: {missing_labels}")

col1, col2 = st.columns(2)
with col1:
    if st.button("Back to Address Intake"):
        st.switch_page("pages/1_address_intake.py")
with col2:
    if st.session_state.get("subject_profile", {}).get("subject_profile_ready"):
        st.success("Ready for Module 3 handoff.")
    else:
        st.warning("Subject is not locked yet. Do not proceed to valuation.")
