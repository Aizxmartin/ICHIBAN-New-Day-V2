import sys
from pathlib import Path
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.address_subject_profile import blank_subject_profile

st.set_page_config(page_title="ICHIBAN - Address Intake", page_icon="🏡", layout="wide")

st.title("Module 1 — Address Intake")
st.subheader("Start with the property address")

st.markdown(
    '''
This intake is intentionally simpler.

### Step 1
Enter the property address.

### What happens next
ICHIBAN will build a subject profile shell and move to verification.

Later, this page can be upgraded to:
- address lookup
- public record verification
- Redfin / Zillow assist
- AVM integration
'''
)

address = st.text_input(
    "Property Address",
    value=st.session_state.get("subject_address", ""),
    placeholder="Example: 2524 S Krameria St, Denver, CO 80222",
)

notes = st.text_area(
    "Optional note",
    value=st.session_state.get("subject_address_note", ""),
    placeholder="Any quick note about the subject property or source of the address.",
    height=120,
)

col1, col2 = st.columns([1, 2])

with col1:
    if st.button("Build Subject Profile", type="primary"):
        if not address.strip():
            st.error("Please enter a property address first.")
        else:
            st.session_state["subject_address"] = address.strip()
            st.session_state["subject_address_note"] = notes.strip()
            st.session_state["subject_profile"] = blank_subject_profile(address.strip())
            st.success("Address accepted. Opening subject verification...")
            st.switch_page("pages/2_subject_verification.py")

with col2:
    st.info("This page is designed to stay light and non-intimidating.")
