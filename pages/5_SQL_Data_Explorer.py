"""
pages/5_SQL_Data_Explorer.py  –  SQL & Data Explorer
"""
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="SQL Explorer · Business Analyst Agent",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.shared import GLOBAL_CSS, render_sidebar, init_session, page_header, get_active_meta

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session()
render_sidebar()

active_tbl, catalog, roles, measures, dates, dimensions, row_count = get_active_meta()

page_header(
    "🛠️", "SQL & Data Explorer",
    f"Run ad-hoc DuckDB queries on your active table.",
)

if not active_tbl:
    st.info(
        "No active dataset. Upload a file and run **Phase 1 ETL** from the sidebar."
    )
    st.stop()

# ── Layout: query panel (left) | results (right) ──────────────────────────────
col_q, col_r = st.columns([1, 1.4], gap="large")

# ════════════════════════════════════════════════════════════════════════════════
# LEFT – QUERY BUILDER
# ════════════════════════════════════════════════════════════════════════════════
with col_q:
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:13px;font-weight:700;color:#0f172a;margin:0 0 10px;'>"
            "📋 Every Preset</p>",
            unsafe_allow_html=True,
        )

        # Build presets from live schema
        presets: dict[str, str] = {
            "Preview First 20 Rows":
                f'SELECT * FROM "{active_tbl}" LIMIT 20',
            "Row Count":
                f'SELECT COUNT(*) AS total_rows FROM "{active_tbl}"',
        }
        if measures:
            presets["Measure Summary (SUM / AVG / MIN / MAX)"] = (
                "SELECT\n" +
                ",\n".join(
                    f'  SUM("{m}") AS sum_{m},\n'
                    f'  AVG("{m}") AS avg_{m},\n'
                    f'  MIN("{m}") AS min_{m},\n'
                    f'  MAX("{m}") AS max_{m}'
                    for m in measures[:3]
                ) +
                f'\nFROM "{active_tbl}"'
            )
        if measures and dimensions:
            presets[f"▶ Products by {measures[0]}"] = (
                f'SELECT "{dimensions[0]}",\n'
                f'       SUM("{measures[0]}") AS total_{measures[0]},\n'
                f'       COUNT(*) AS count\n'
                f'FROM "{active_tbl}"\n'
                f'GROUP BY 1\n'
                f'ORDER BY 2 DESC\n'
                f'LIMIT 20'
            )
        if measures and dates:
            presets[f"📅 Monthly {measures[0]}"] = (
                f"SELECT strftime('%Y-%m', CAST(\"{dates[0]}\" AS DATE)) AS month,\n"
                f'       SUM("{measures[0]}") AS total\n'
                f'FROM "{active_tbl}"\n'
                f'GROUP BY 1\n'
                f'ORDER BY 1'
            )
        if dimensions:
            presets[f"Distinct {dimensions[0]} values"] = (
                f'SELECT DISTINCT "{dimensions[0]}" FROM "{active_tbl}" LIMIT 50'
            )
        if measures:
            presets["Null Check (all measure cols)"] = "\nUNION ALL\n".join(
                f'SELECT \'{m}\' AS col, COUNT(*) AS nulls '
                f'FROM "{active_tbl}" WHERE "{m}" IS NULL'
                for m in measures
            )

        chosen = st.selectbox("Pre-built Queries", list(presets.keys()),
                              key="sql_preset")

    with st.container(border=True):
        st.markdown(
            "<p style='font-size:13px;font-weight:700;color:#0f172a;margin:0 0 6px;'>"
            "✏️ SQL Editor</p>",
            unsafe_allow_html=True,
        )
        sql_input = st.text_area(
            "SQL",
            value=presets[chosen],
            height=200,
            label_visibility="collapsed",
            key="sql_editor",
        )

        btn_c1, btn_c2 = st.columns([1, 1])
        run_btn   = btn_c1.button("▶ Execute Query", type="primary",
                                  width='stretch', key="run_sql")
        clear_btn = btn_c2.button("✖ Clear Results", width='stretch',
                                  key="clear_sql")

        if clear_btn and "sql_result" in st.session_state:
            del st.session_state["sql_result"]
            st.rerun()

        if run_btn:
            try:
                res_df = st.session_state.db.conn.execute(sql_input).df()
                st.session_state["sql_result"] = res_df
                st.rerun()
            except Exception as exc:
                st.error(f"SQL Error: {exc}")
                if "sql_result" in st.session_state:
                    del st.session_state["sql_result"]

        # Schema quick-reference
        with st.expander("📖 Table Schema Reference", expanded=False):
            cols_info = catalog.get("columns", [])
            if cols_info:
                import pandas as pd
                schema_df = pd.DataFrame([{
                    "Column":    c.get("name"),
                    "Type":      c.get("type"),
                    "Role":      c.get("role", "").upper(),
                    "Null %":    f"{c.get('null_pct', 0):.0f}%",
                } for c in cols_info])
                st.dataframe(schema_df, width='stretch',
                             hide_index=True, height=250)
            else:
                st.caption("Run Phase 1 ETL to see the schema here.")

# ════════════════════════════════════════════════════════════════════════════════
# RIGHT – RESULTS
# ════════════════════════════════════════════════════════════════════════════════
with col_r:
    with st.container(border=True):
        st.markdown(
            "<p style='font-size:13px;font-weight:700;color:#0f172a;margin:0 0 6px;'>"
            "📊 Query Results</p>",
            unsafe_allow_html=True,
        )

        if "sql_result" in st.session_state:
            res_df = st.session_state["sql_result"]
            st.success(
                f"Returned **{len(res_df):,} rows** · {len(res_df.columns)} columns"
            )
            st.dataframe(res_df, width='stretch', height=320)

            # Export
            csv_bytes = res_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Export Info",
                data=csv_bytes,
                file_name="query_results.csv",
                mime="text/csv",
                width='stretch',
                key="export_csv",
            )

            # Auto-visualize
            num_cols = res_df.select_dtypes(include="number").columns.tolist()
            cat_cols = res_df.select_dtypes(exclude="number").columns.tolist()

            if num_cols and cat_cols and len(res_df) > 1:
                st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
                with st.expander("📈 Auto-Visualize Results", expanded=True):
                    vc1, vc2, vc3 = st.columns(3)
                    x_col      = vc1.selectbox("X axis",      cat_cols, key="viz_x")
                    y_col      = vc2.selectbox("Y axis",      num_cols, key="viz_y")
                    chart_type = vc3.radio("Type", ["Bar","Line","Scatter"],
                                           horizontal=True, key="viz_type")

                    if chart_type == "Bar":
                        fig = px.bar(res_df, x=x_col, y=y_col,
                                     color_discrete_sequence=["#2563eb"])
                    elif chart_type == "Line":
                        fig = px.line(res_df, x=x_col, y=y_col,
                                      color_discrete_sequence=["#2563eb"],
                                      markers=True)
                    else:
                        fig = px.scatter(res_df, x=x_col, y=y_col,
                                         color_discrete_sequence=["#2563eb"])

                    fig.update_layout(
                        template="plotly_white",
                        height=300,
                        margin=dict(l=10, r=10, t=30, b=10),
                    )
                    st.plotly_chart(fig, width='stretch',
                                    key="auto_viz_chart")
        else:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;
                        justify-content:center;height:400px;text-align:center;
                        color:#94a3b8;">
                <div style="font-size:38px;margin-bottom:12px;">🛠️</div>
                <div style="font-size:14px;font-weight:600;color:#475569;
                            margin-bottom:6px;">No query run yet</div>
                <div style="font-size:12.5px;line-height:1.6;">
                    Select a preset or write a query on the left,<br>
                    then click <strong>▶ Execute Query</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)
