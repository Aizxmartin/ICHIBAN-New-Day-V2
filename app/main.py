import streamlit as st

st.set_page_config(page_title="ICHIBAN - Address First", page_icon="🏡", layout="wide")

st.title("ICHIBAN — Address-First Intake")
st.subheader("A simpler starting point for subject property validation")

st.markdown(
    '''
### Welcome
This build starts with the property address first.

The goal is to:
- reduce intake friction
- verify the subject property before valuation work begins
- ask for MLS and support files only after the subject profile is grounded

Use the page menu on the left to begin with:
**1_address_intake**
'''
)

st.info("This is the clean starter repo for the new address-first design.")
