import streamlit as st

st.set_page_config(page_title="ICHIBAN - Address First", page_icon="🏡", layout="wide")

st.title("ICHIBAN — Address-First Intake")
st.subheader("A simpler starting point for subject property validation")

DEFAULT_REPORT_TYPE = "Seller Report Package — Full Default"

if "report_type_selection" not in st.session_state:
    st.session_state["report_type_selection"] = DEFAULT_REPORT_TYPE

st.markdown(
    '''
### Welcome
This build starts with the property address first.

The goal is to:
- reduce intake friction
- verify the subject property before valuation work begins
- keep the Valuation Comp File separate from the broader 1004MC / Competition Market File
- default to the seller-facing report package unless the user chooses otherwise

Use the page menu on the left to begin with:
**1_address_intake**
'''
)

st.info("Default Report Type: Seller Report Package — Full Default")

with st.expander("Current file-role workflow", expanded=True):
    st.markdown(
        '''
**Valuation Comp File**  
Used for adjusted comps, Ruler Range, and recommended value range.

**1004MC / Competition Market File**  
Used for market pattern, absorption, current competition, projected MOI range, seller caveats, and momentum discussion.

**Report language rule**  
The value range is based on closed comparable evidence. The market momentum section reviews a broader competitive pool to evaluate current inventory pressure, pending activity, recent sales pace, and market direction.
'''
    )
