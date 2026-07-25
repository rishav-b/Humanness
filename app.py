import streamlit as st
import pandas as pd

if "expd" not in st.session_state:
    st.session_state.expd = pd.DataFrame( 
            data = {
            "Cohort #": [],
            "# Samples in Group 1": [],
            "# Samples in Group 2": [],
            "Train/Test": [],
            },
        )


st.set_page_config(
    page_title="COMPASS Humanness Calculator",
    page_icon="",
    layout="centered"
)

st.header("COMPASS Humanness Calculator")
st.text("Text about CHC text about CHC")

expd, hum, rel, nam = st.tabs(["Experimental Design", "Humanness", "Relevance", "NAM Fidelity"])

with expd:
    st.dataframe(st.session_state.expd)

    with st.container(border=True):
        g1 = st.number_input("# Samples in Group 1", min_value = 0)
        g2 = st.number_input("# Samples in Group 2", min_value = 0)
        t = st.selectbox(label="Train/Test", options = ["Train", "Test"])
        if st.button("+ Add Cohort", type = "primary"):
            expd = st.session_state.expd
            st.session_state.expd.loc[len(expd)] = {"Cohort #": len(expd)+1, "# Samples in Group 1": g1, "# Samples in Group 2": g2, "Train/Test": t}
            st.rerun()


st.markdown(
    """
    <style>
    h1, h2, h3 {
        color: rgb(8, 38, 74) !important;
    }

    h3 {
        font-size: 16px !important;
        text-transform: uppercase !important;
        letter-spacing: 1.32px !important;
    }
    """,
    unsafe_allow_html=True
)

