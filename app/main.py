import streamlit as st

from ui_theme import apply_ichiban_theme, ichiban_hero

st.set_page_config(page_title="ICHIBAN - Address First", page_icon="🏡", layout="wide")

apply_ichiban_theme()


ichiban_hero("Address-First Intake", "A calmer, cleaner starting point for subject property validation and Tarzan-first valuation work.")

DEFAULT_REPORT_TYPE = "Tarzan Valuation Analysis"

if "report_type_selection" not in st.session_state:
    st.session_state["report_type_selection"] = DEFAULT_REPORT_TYPE

st.markdown(
    '''
### Welcome
This build starts with the property address first.

The goal is to:
- reduce intake friction
- verify the subject property before valuation work begins
- ask for MLS and support files only after the subject profile is grounded
- keep the Valuation Comp File separate from the broader 1004MC / Competition Market File
- default to the Tarzan Valuation Analysis standard

Use the page menu on the left to begin with:
**1_address_intake**
'''
)

st.info("Report Standard: Tarzan Valuation Analysis")

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
