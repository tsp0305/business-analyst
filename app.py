"""
app.py  –  Business Analyst Agent
Unified, production-grade SaaS cockpit matching the exact design and flow.
"""
import streamlit as st

st.set_page_config(
    page_title="Business Analyst Agent",
    page_icon="✦",
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
    render_dashboard_view,
    render_sql_view,
    render_process_flow_view,
)

# ── 1. Global CSS & Session Initialization ────────────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session()

# ── 2. Sidebar Navigation & Data Controls ─────────────────────────────────────
render_sidebar()

# ── 3. Top Header Bar ─────────────────────────────────────────────────────────
page_header(
    icon="✦",
    title="Business Analyst Agent",
    subtitle="Turn your data into actionable insights",
)

# ── 4. Process Status Pipeline Stepper (The Neat Flow of All Processes) ────────
render_process_flow_banner()

# ── 5. Main View Router ───────────────────────────────────────────────────────
current_page = st.session_state.get("current_page", "💬 BI Analyst Chat")

if current_page == "💬 BI Analyst Chat":
    render_cockpit_view()
elif current_page == "📊 BI Analytics Dashboard":
    render_dashboard_view()
elif current_page == "</> SQL & Data Explorer":
    render_sql_view()
elif current_page == "🔄 Process Flow & Status":
    render_process_flow_view()
else:
    render_cockpit_view()
