"""
tests/test_ui.py
Smoke tests for the multipage Streamlit application.
Each page is tested individually via AppTest.from_file().
"""
import pytest

try:
    from streamlit.testing.v1 import AppTest
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

TIMEOUT = 60  # seconds per page test


# ─────────────────────────────────────────────────────────────────────────────
# Home page
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_home_page_renders():
    """Home page renders without exceptions and has the ETL sidebar button."""
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"Home page raised: {at.exception}"

    sidebar_btn_labels = [b.label for b in at.sidebar.button]
    assert "Run Phase 1 (ETL) on Uploaded Data" in sidebar_btn_labels, (
        f"ETL button missing. Found: {sidebar_btn_labels}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# BI Analyst Chat page
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_chat_page_renders():
    """Chat page renders and has a chat_input widget."""
    at = AppTest.from_file("pages/2_BI_Analyst_Chat.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"Chat page raised: {at.exception}"

    # Must have the sidebar ETL button
    sidebar_btn_labels = [b.label for b in at.sidebar.button]
    assert "Run Phase 1 (ETL) on Uploaded Data" in sidebar_btn_labels

    # Must have at least one chat_input
    assert len(at.chat_input) >= 1, "Chat page must have a chat_input widget"


# ─────────────────────────────────────────────────────────────────────────────
# Data Cleaning & Profiling page (removed from nav, file kept as redirect)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_data_cleaning_page_renders():
    """Redirect page renders without exceptions (Data Cleaning removed from nav)."""
    at = AppTest.from_file("pages/3_Data_Cleaning_Profiling.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"Data Cleaning redirect page raised: {at.exception}"


# ─────────────────────────────────────────────────────────────────────────────
# BI Analytics Dashboard page
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_dashboard_page_renders():
    """Dashboard page renders without exceptions."""
    at = AppTest.from_file("pages/4_BI_Analytics_Dashboard.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"Dashboard page raised: {at.exception}"


# ─────────────────────────────────────────────────────────────────────────────
# SQL & Data Explorer page
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_sql_explorer_page_renders():
    """SQL Explorer page renders without exceptions."""
    at = AppTest.from_file("pages/5_SQL_Data_Explorer.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"SQL Explorer page raised: {at.exception}"


# ─────────────────────────────────────────────────────────────────────────────
# Settings page
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAS_STREAMLIT, reason="Streamlit not installed")
def test_settings_page_renders():
    """Settings page renders and has a Save Settings button."""
    at = AppTest.from_file("pages/6_Settings.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"Settings page raised: {at.exception}"

    all_btn_labels = [b.label for b in at.button]
    assert any("Save" in lbl for lbl in all_btn_labels), (
        f"Save button missing on Settings page. Buttons: {all_btn_labels}"
    )
