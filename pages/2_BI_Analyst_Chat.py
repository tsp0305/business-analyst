"""
pages/2_BI_Analyst_Chat.py  –  BI Analyst Chat
"""
import streamlit as st

st.set_page_config(
    page_title="BI Analyst Chat · Business Analyst Agent",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.shared import (
    GLOBAL_CSS,
    render_sidebar,
    init_session,
    page_header,
    render_process_flow_banner,
    render_cockpit_view,
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session()
render_sidebar()
page_header("💬", "BI Analyst Chat", "Ask questions, get insights, charts and recommendations.")
render_process_flow_banner()
render_cockpit_view()
