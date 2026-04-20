import sys
from pathlib import Path
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.address_subject_profile import blank_subject_profile, missing_required_fields, subject_profile_ready
from core.subject_requirements import FIELD_LABELS, REQUIRED_SUBJECT_FIELDS, OPTIONAL_SUBJECT_FIELDS

st.set_page_config(page_title="ICHIBAN - Subject Verification", page_icon="🏡", layout="wide")

st.title("Module 2 — Subject Verification")
st.subheader("Build the subject profile before valuation begins")

profile = st.session_state.get("subject_profile")
if not profile:
    address = st.session_state.get("subject_address", "")
    if not address:
        st.error("No subject address was found in session. Please return to Module 1.")
        st.stop()
    profile = blank_subject_profile(address)

st.markdown(
    '''
### Verification Layer
This page is where ICHIBAN confirms the subject property's core facts.

For now, this starter version supports:
- address confirmation
- manual verified entry
- subject readiness logic

Later, this page can be upgraded to:
- public-record lookup
- Redfin / Zillow assist
- PDF extraction comparison
- confidence scoring
'''
)

left, right = st.columns([1.1, 1])

with left:
    st.markdown("#### Current Subject Profile")
    rows = []
    for field in REQUIRED_SUBJECT_FIELDS + OPTIONAL_SUBJECT_FIELDS:
        rows.append([
            FIELD_LABELS.get(field, field),
            profile.get(field),
            profile.get("field_sources", {}).get(field, ""),
        ])
    df = pd.DataFrame(rows, columns=["Field", "Current Value", "Source"])
    st.dataframe(df, width="stretch", hide_index=True)

with right:
    st.markdown("#### Enter / Confirm Subject Data")
    subject_address = st.text_input("Subject Address", value=profile.get("subject_address") or "")
    above_grade_sqft = st.number_input("Above Grade SqFt", min_value=0, step=1, value=int(profile.get("above_grade_sqft") or 0))
    beds = st.number_input("Bedrooms", min_value=0.0, step=1.0, value=float(profile.get("beds") or 0.0))
    baths = st.number_input("Bathrooms", min_value=0.0, step=0.5, value=float(profile.get("baths") or 0.0))
    year_built = st.number_input("Year Built", min_value=0, step=1, value=int(profile.get("year_built") or 0))
    real_avm = st.number_input("RealAVM", min_value=0, step=1000, value=int(profile.get("real_avm") or 0))
    real_avm_low = st.number_input("RealAVM Range Low", min_value=0, step=1000, value=int(profile.get("real_avm_range_low") or 0))
    real_avm_high = st.number_input("RealAVM Range High", min_value=0, step=1000, value=int(profile.get("real_avm_range_high") or 0))
    lot_size_sqft = st.number_input("Lot Size SqFt", min_value=0, step=1, value=int(profile.get("lot_size_sqft") or 0))
    style = st.text_input("Style", value=profile.get("style") or "")
    stories = st.text_input("Stories", value=profile.get("stories") or "")
    property_type = st.text_input("Property Type", value=profile.get("property_type") or "")

if st.button("Save Verified Subject Profile", type="primary"):
    updated = dict(profile)
    updated["subject_address"] = subject_address.strip() or None
    updated["above_grade_sqft"] = None if above_grade_sqft == 0 else above_grade_sqft
    updated["beds"] = None if beds == 0 else beds
    updated["baths"] = None if baths == 0 else baths
    updated["year_built"] = None if year_built == 0 else year_built
    updated["real_avm"] = None if real_avm == 0 else real_avm
    updated["real_avm_range_low"] = None if real_avm_low == 0 else real_avm_low
    updated["real_avm_range_high"] = None if real_avm_high == 0 else real_avm_high
    updated["lot_size_sqft"] = None if lot_size_sqft == 0 else lot_size_sqft
    updated["style"] = style.strip() or None
    updated["stories"] = stories.strip() or None
    updated["property_type"] = property_type.strip() or None

    for field in FIELD_LABELS:
        if field in updated:
            updated.setdefault("field_sources", {})[field] = "verified_entry"

    updated["subject_profile_ready"] = subject_profile_ready(updated)
    st.session_state["subject_profile"] = updated

    missing = missing_required_fields(updated)
    if missing:
        labels = ", ".join(FIELD_LABELS.get(f, f) for f in missing)
        st.error(f"Subject profile is not ready yet. Missing required fields: {labels}")
    else:
        st.success("Subject profile is ready for the next stage.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Back to Address Intake"):
        st.switch_page("pages/1_address_intake.py")
with col2:
    if st.session_state.get("subject_profile", {}).get("subject_profile_ready"):
        st.success("Ready for the next module.")
    else:
        st.warning("Complete the required subject fields before handoff.")
