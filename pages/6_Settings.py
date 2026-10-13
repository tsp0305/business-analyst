"""
pages/6_Settings.py  –  Settings
"""
import streamlit as st
import sys
import platform

st.set_page_config(
    page_title="Settings · Business Analyst Agent",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.shared import GLOBAL_CSS, render_sidebar, init_session, page_header

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session()
render_sidebar()

page_header(
    "⚙️", "Settings",
    "Configure API keys, model selection, data preferences, and security options.",
)

settings = st.session_state.get("settings", {})

# ── Layout: left (config) | right (system info) ───────────────────────────────
col_cfg, col_sys = st.columns([1.2, 1], gap="large")

# ════════════════════════════════════════════════════════════════════════════════
# LEFT – CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════
with col_cfg:

    # ── LLM ──────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "🤖 LLM Configuration</p>",
            unsafe_allow_html=True,
        )
        api_key = st.text_input(
            "Gemini API Key",
            value=st.session_state.api_key,
            type="password",
            help="Get your key at https://aistudio.google.com/",
            key="settings_api_key",
        )
        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key

        model = st.selectbox(
            "Model",
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
            index=["gemini-2.5-flash","gemini-2.5-pro","gemini-1.5-flash"].index(
                st.session_state.get("selected_model", "gemini-2.5-flash")
            ),
            key="settings_model",
        )
        st.session_state.selected_model = model

        if st.session_state.api_key:
            st.success("✅ API key configured — Gemini Mode active.")
        else:
            st.info("ℹ️ No API key — running in Schema Planner Mode (free, offline).")

    # ── Application ───────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "🔧 Application Settings</p>",
            unsafe_allow_html=True,
        )
        max_steps = st.slider(
            "Max Agent Steps",
            min_value=3, max_value=20,
            value=settings.get("max_steps", 8),
            step=1,
            key="settings_max_steps",
        )
        settings["max_steps"] = max_steps

        st.markdown(
            "<p style='font-size:12px;color:#64748b;margin:-8px 0 12px;'>"
            "Controls the maximum reasoning steps per agent run.</p>",
            unsafe_allow_html=True,
        )

        layout_wide = st.toggle(
            "Wide layout (full viewport)",
            value=True,
            key="settings_wide",
            disabled=True,  # always wide in this app
        )

    # ── Data & Security ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "🔒 Data & Security</p>",
            unsafe_allow_html=True,
        )
        cleaning = st.toggle(
            "Enable Data Cleaning (Phase 1)",
            value=settings.get("enable_data_cleaning", True),
            key="settings_cleaning",
        )
        settings["enable_data_cleaning"] = cleaning

        sql_guard = st.toggle(
            "Enable SQL Guard (AST Validator)",
            value=settings.get("enable_sql_guard", True),
            key="settings_sql_guard",
        )
        settings["enable_sql_guard"] = sql_guard

        st.markdown(
            "<p style='font-size:12px;color:#64748b;margin-top:4px;line-height:1.5;'>"
            "SQL Guard uses AST-level parsing to block DDL/DML and "
            "file-loading functions.</p>",
            unsafe_allow_html=True,
        )

    # ── Save ──────────────────────────────────────────────────────────────────
    if st.button("💾 Save Settings", type="primary", use_container_width=True,
                 key="save_settings"):
        st.session_state.settings = settings
        st.success("Settings saved!")

# ════════════════════════════════════════════════════════════════════════════════
# RIGHT – SYSTEM INFO + DATASET MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════
with col_sys:

    # ── System Info ───────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "🖥️ System Information</p>",
            unsafe_allow_html=True,
        )
        try:
            import duckdb
            ddb_ver = duckdb.__version__
        except Exception:
            ddb_ver = "unknown"
        try:
            import streamlit as _st
            st_ver = _st.__version__
        except Exception:
            st_ver = "unknown"
        try:
            import google.generativeai as _g
            genai_ver = _g.__version__
        except Exception:
            try:
                import google.genai as _g2
                genai_ver = _g2.__version__
            except Exception:
                genai_ver = "not installed"

        st.markdown(f"""
        | Component | Version |
        |---|---|
        | Python | `{sys.version.split()[0]}` |
        | Streamlit | `{st_ver}` |
        | DuckDB | `{ddb_ver}` |
        | Google GenAI | `{genai_ver}` |
        | Platform | `{platform.system()} {platform.release()}` |
        """)

    # ── Active Dataset Info ───────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "📂 Loaded Datasets</p>",
            unsafe_allow_html=True,
        )
        all_tables = st.session_state.db.list_tables()
        if all_tables:
            for tbl in all_tables:
                is_active = (tbl == st.session_state.active_table)
                badge     = "🟢 **active**" if is_active else "⚪ loaded"
                try:
                    n = st.session_state.db.conn.execute(
                        f'SELECT COUNT(*) FROM "{tbl}"'
                    ).fetchone()[0]
                    st.markdown(
                        f"- `{tbl}` — {n:,} rows {badge}"
                    )
                except Exception:
                    st.markdown(f"- `{tbl}` {badge}")

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("🗑️ Clear All Datasets", use_container_width=True,
                         key="clear_datasets"):
                try:
                    for tbl in all_tables:
                        st.session_state.db.conn.execute(f'DROP TABLE IF EXISTS "{tbl}"')
                    st.session_state.active_table = None
                    st.session_state.catalogs     = {}
                    st.success("All datasets cleared.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing datasets: {e}")
        else:
            st.info("No datasets loaded yet.")

    # ── Chat management ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:14px;font-weight:700;color:#0f172a;margin:0 0 12px;'>"
            "💬 Chat History</p>",
            unsafe_allow_html=True,
        )
        n_msgs = len(st.session_state.chat_history)
        st.markdown(
            f"<p style='font-size:13px;color:#475569;'>{n_msgs} messages in history.</p>",
            unsafe_allow_html=True,
        )
        if n_msgs:
            if st.button("🗑️ Clear Chat History", use_container_width=True,
                         key="settings_clear_chat"):
                st.session_state.chat_history = []
                st.success("Chat history cleared.")
                st.rerun()
