"""
pages/3_Data_Cleaning_Profiling.py
This page has been removed from the navigation menu.
Redirects to the Home page.
"""
import streamlit as st

st.set_page_config(
    page_title="Business Analyst Agent",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.shared import GLOBAL_CSS, render_sidebar, init_session, page_header

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session()
render_sidebar()

page_header("✦", "Business Analyst Agent", "Turn your data into actionable insights.")

st.info("The Data Cleaning & Profiling view has been removed. Use the sidebar to navigate to another page.")
