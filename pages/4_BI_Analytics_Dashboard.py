"""
pages/4_BI_Analytics_Dashboard.py  –  Interactive BI Analytics Dashboard
Separate page with:
  - Auto-generated KPI cards and smart charts from any loaded dataset
  - Custom Chart Builder: choose chart type + measure + dimension + aggregation
  - Chart Test Harness: run assertions against the generated charts
"""
import streamlit as st

st.set_page_config(
    page_title="Analytics Dashboard · Business Analyst Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
from datetime import datetime

from utils.shared import (
    GLOBAL_CSS,
    render_sidebar,
    init_session,
    page_header,
    get_active_meta,
    get_dynamic_analytics,
)

# ── Bootstrap ──────────────────────────────────────────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.dash-section-header {
    font-size: 15px; font-weight: 700; color: #0f172a;
    margin: 24px 0 10px; padding-bottom: 8px;
    border-bottom: 2px solid #e2e8f0;
    display: flex; align-items: center; gap: 8px;
}
.builder-panel {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 14px; padding: 20px 22px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 20px;
}
.chart-card {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 16px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04); margin-bottom: 16px;
}
.chart-card-title {
    font-size: 12.5px; font-weight: 700; color: #0f172a;
    margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
}
.kpi-dash-card {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 16px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.kpi-dash-label { font-size: 11.5px; font-weight: 600; color: #64748b; margin-bottom: 6px; }
.kpi-dash-value { font-size: 22px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em; margin-bottom: 4px; }
.kpi-dash-delta { font-size: 11px; font-weight: 600; color: #10b981; }
.no-data-banner {
    background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
    border: 1.5px dashed #bfdbfe; border-radius: 14px;
    padding: 40px 30px; text-align: center; margin: 20px 0;
}
.no-data-icon { font-size: 42px; margin-bottom: 10px; }
.no-data-title { font-size: 16px; font-weight: 700; color: #1e3a8a; margin-bottom: 6px; }
.no-data-sub { font-size: 12.5px; color: #64748b; }
.harness-result-pass {
    background: #052e16; border: 1px solid #15803d; border-radius: 8px;
    padding: 8px 14px; font-size: 12px; color: #86efac; font-weight: 600;
    margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
}
.harness-result-fail {
    background: #450a0a; border: 1px solid #b91c1c; border-radius: 8px;
    padding: 8px 14px; font-size: 12px; color: #fca5a5; font-weight: 600;
    margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
}
.harness-result-warn {
    background: #1c1002; border: 1px solid #b45309; border-radius: 8px;
    padding: 8px 14px; font-size: 12px; color: #fcd34d; font-weight: 600;
    margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
}
.insights-list { list-style: none; padding: 0; margin: 0; }
.insights-list li {
    font-size: 12.5px; color: #334155; padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
    display: flex; align-items: flex-start; gap: 8px; line-height: 1.5;
}
.insights-list li:last-child { border-bottom: none; }
.insight-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #2563eb;
    flex-shrink: 0; margin-top: 5px;
}
.rec-card {
    background: linear-gradient(135deg, #eff6ff, #f0fdf4);
    border: 1px solid #bfdbfe; border-radius: 10px; padding: 14px 16px;
    font-size: 12.5px; color: #1e3a8a; line-height: 1.6; margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

init_session()
render_sidebar()

# ── Page Header ────────────────────────────────────────────────────────────────
page_header(
    "📊", "BI Analytics Dashboard",
    "Interactive analytics — choose chart types, custom params, and run the test harness.",
)

# ── Fetch Active Data ──────────────────────────────────────────────────────────
active_tbl, catalog, roles, measures, dates, dimensions, row_count = get_active_meta()

# ── No Dataset Loaded Banner ───────────────────────────────────────────────────
if not active_tbl:
    st.markdown("""
    <div class="no-data-banner">
        <div class="no-data-icon">📁</div>
        <div class="no-data-title">No Dataset Loaded</div>
        <div class="no-data-sub">Upload a CSV, XLSX, TSV, Parquet, or JSON file using the sidebar.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Fetch Analytics ────────────────────────────────────────────────────────────
dyn = get_dynamic_analytics(st.session_state.db, active_tbl)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_overview, tab_builder, tab_harness = st.tabs([
    "📊 Dashboard Overview",
    "🛠️ Custom Chart Builder",
    "🧪 Chart Test Harness",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:

    st.markdown("<div class='dash-section-header'>⚡ Key Metrics</div>", unsafe_allow_html=True)
    kpi_cols = st.columns(4, gap="medium")
    for i, kpi in enumerate(dyn["kpis"][:4]):
        with kpi_cols[i]:
            st.markdown(f"""
            <div class="kpi-dash-card">
                <div class="kpi-dash-label">{kpi['icon']} {kpi['label']}</div>
                <div class="kpi-dash-value">{kpi['val']}</div>
                <div class="kpi-dash-delta">{kpi['delta']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dash-section-header'>📈 Trend & Distribution</div>", unsafe_allow_html=True)
    r1c1, r1c2 = st.columns(2, gap="medium")

    with r1c1:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='chart-card-title'>📈 {dyn['p_label']} Trend</div>",
                    unsafe_allow_html=True)
        if dyn["trend_fig"]:
            fig = dyn["trend_fig"]
            fig.update_layout(height=270)
            st.plotly_chart(fig, width='stretch', key="ov_trend")
        st.markdown("</div>", unsafe_allow_html=True)

    with r1c2:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='chart-card-title'>🏷️ {dyn['p_label']} by {dyn['dim_label']}</div>",
                    unsafe_allow_html=True)
        if dyn["cat_fig"]:
            fig2 = dyn["cat_fig"]
            fig2.update_layout(height=270)
            st.plotly_chart(fig2, width='stretch', key="ov_cat")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='dash-section-header'>🔍 Outliers & Forecast</div>", unsafe_allow_html=True)
    r2c1, r2c2 = st.columns(2, gap="medium")

    with r2c1:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown("<div class='chart-card-title'>🚨 Outlier Detection Radar</div>",
                    unsafe_allow_html=True)
        if dyn["radar_fig"]:
            fig3 = dyn["radar_fig"]
            fig3.update_layout(height=270)
            st.plotly_chart(fig3, width='stretch', key="ov_radar")
        st.markdown("</div>", unsafe_allow_html=True)

    with r2c2:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='chart-card-title'>🔮 {dyn['p_label']} Forecast</div>",
                    unsafe_allow_html=True)
        if dyn["forecast_fig"]:
            fig4 = dyn["forecast_fig"]
            fig4.update_layout(height=270)
            st.plotly_chart(fig4, width='stretch', key="ov_fore")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='dash-section-header'>🏆 Top Segments & Insights</div>", unsafe_allow_html=True)
    r3c1, r3c2 = st.columns([1.3, 1], gap="medium")

    with r3c1:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='chart-card-title'>🏆 Top {dyn['dim_label']}s by {dyn['p_label']}</div>",
                    unsafe_allow_html=True)
        for row in dyn.get("top_rows", []):
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid #f1f5f9;'>
                <div style='width:22px;height:22px;background:#eff6ff;border-radius:6px;
                            display:flex;align-items:center;justify-content:center;
                            font-size:11px;font-weight:700;color:#2563eb;flex-shrink:0;'>{row['rank']}</div>
                <div style='flex:1;min-width:0;'>
                    <div style='font-size:12.5px;font-weight:600;color:#0f172a;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{row['item']}</div>
                    <div style='margin-top:3px;background:#e2e8f0;border-radius:3px;height:4px;'>
                        <div style='width:{row["width_pct"]}%;background:linear-gradient(90deg,#2563eb,#3b82f6);
                                    height:4px;border-radius:3px;'></div>
                    </div>
                </div>
                <div style='text-align:right;flex-shrink:0;'>
                    <div style='font-size:12.5px;font-weight:700;color:#0f172a;'>{row['val_str']}</div>
                    <div style='font-size:10.5px;color:#64748b;'>{row['pct']}%</div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with r3c2:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown("<div class='chart-card-title'>⚡ Automated Insights</div>",
                    unsafe_allow_html=True)
        items_html = "".join(
            f"<li><span class='insight-dot'></span>{ins}</li>"
            for ins in dyn.get("insights", [])
        )
        st.markdown(f"<ul class='insights-list'>{items_html}</ul>", unsafe_allow_html=True)
        if dyn.get("recommendation"):
            st.markdown(
                f"<div class='rec-card'>💡 <strong>Recommendation:</strong> {dyn['recommendation']}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – CUSTOM CHART BUILDER
# ══════════════════════════════════════════════════════════════════════════════
with tab_builder:
    st.markdown("<div class='dash-section-header'>🛠️ Build Your Custom Chart</div>",
                unsafe_allow_html=True)
    st.markdown("<p style='font-size:12.5px;color:#64748b;margin-top:-6px;margin-bottom:16px;'>"
                "Choose chart type, measure, dimension and aggregation to generate a live Plotly chart.</p>",
                unsafe_allow_html=True)

    CHART_TYPES = {
        "📊 Bar": "bar",
        "📈 Line": "line",
        "🔵 Scatter": "scatter",
        "🥧 Pie": "pie",
        "🎻 Box Plot": "box",
        "🌡️ Heatmap": "heatmap",
        "📉 Area": "area",
        "🔢 Histogram": "histogram",
    }

    # ── Controls ────────────────────────────────────────────────────────────────
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns(4, gap="medium")

    with ctrl_col1:
        chart_type_label = st.selectbox("Chart Type", list(CHART_TYPES.keys()), key="builder_chart_type")
        chart_type = CHART_TYPES[chart_type_label]

    # Detect columns
    all_cols = []
    if active_tbl and st.session_state.db.table_exists(active_tbl):
        try:
            df_schema = st.session_state.db.conn.execute(f'SELECT * FROM "{active_tbl}" LIMIT 0').df()
            all_cols = list(df_schema.columns)
        except Exception:
            all_cols = measures + dimensions + dates

    numeric_cols = measures if measures else [c for c in all_cols if c not in dimensions + dates]
    cat_cols     = dimensions if dimensions else [c for c in all_cols if c not in numeric_cols + dates]

    with ctrl_col2:
        measure_col = st.selectbox(
            "Measure (Y-axis / Value)",
            numeric_cols or all_cols or ["—"],
            key="builder_measure",
        )

    with ctrl_col3:
        dim_col_options = (cat_cols + dates) if (cat_cols or dates) else all_cols
        dim_label_text = {
            "histogram": "Column to Distribute",
            "scatter": "X-axis Column",
        }.get(chart_type, "Dimension / Group")
        dim_col = st.selectbox(dim_label_text, dim_col_options or all_cols or ["—"], key="builder_dimension")

    with ctrl_col4:
        AGG_OPTIONS = {
            "Sum": "SUM", "Average": "AVG", "Count": "COUNT",
            "Max": "MAX", "Min": "MIN", "Count Distinct": "COUNT_DISTINCT",
        }
        is_raw_chart = chart_type in ("scatter", "box", "histogram")
        agg_choices = ["None (raw values)"] + list(AGG_OPTIONS.keys())
        agg_default = 0 if is_raw_chart else 0  # always index 0 for raw; will override below
        _agg_sel = st.selectbox(
            "Aggregation",
            ["None (raw values)"] if is_raw_chart else list(AGG_OPTIONS.keys()),
            key="builder_agg",
            disabled=is_raw_chart,
        )
        if is_raw_chart:
            agg_label, agg_func = "None (raw)", "NONE"
        else:
            agg_label = _agg_sel
            agg_func  = AGG_OPTIONS[agg_label]

    adv_col1, adv_col2, adv_col3, adv_col4 = st.columns(4, gap="medium")
    with adv_col1:
        top_n = st.slider("Top N groups", 3, 30, 10, key="builder_topn")
    with adv_col2:
        color_scheme = st.selectbox(
            "Color Palette",
            ["Blues", "Viridis", "Plotly", "Set1", "Pastel", "Dark24", "Turbo"],
            key="builder_palette",
        )
    with adv_col3:
        chart_height = st.slider("Chart Height (px)", 250, 700, 380, step=25, key="builder_height")
    with adv_col4:
        show_labels = st.toggle("Show Data Labels", value=True, key="builder_labels")

    gen_btn = st.button("▶  Generate Chart", type="primary", key="btn_gen_chart")

    # ── Chart rendering ─────────────────────────────────────────────────────────
    PALETTE_MAP = {
        "Blues": px.colors.sequential.Blues,
        "Viridis": px.colors.sequential.Viridis,
        "Plotly": px.colors.qualitative.Plotly,
        "Set1": px.colors.qualitative.Set1,
        "Pastel": px.colors.qualitative.Pastel,
        "Dark24": px.colors.qualitative.Dark24,
        "Turbo": px.colors.sequential.Turbo,
    }
    palette = PALETTE_MAP.get(color_scheme, px.colors.qualitative.Plotly)

    if gen_btn or st.session_state.get("builder_last_run"):
        st.session_state["builder_last_run"] = True
        try:
            conn = st.session_state.db.conn
            df_chart = None
            fig_custom = None

            # ── Build query ───────────────────────────────────────────────────
            if chart_type == "histogram":
                df_chart = conn.execute(
                    f'SELECT CAST("{measure_col}" AS DOUBLE) AS val '
                    f'FROM "{active_tbl}" WHERE "{measure_col}" IS NOT NULL LIMIT 5000'
                ).df()
            elif chart_type == "scatter":
                df_chart = conn.execute(
                    f'SELECT CAST("{dim_col}" AS VARCHAR) AS x_val, '
                    f'CAST("{measure_col}" AS DOUBLE) AS y_val '
                    f'FROM "{active_tbl}" '
                    f'WHERE "{measure_col}" IS NOT NULL AND "{dim_col}" IS NOT NULL LIMIT 2000'
                ).df()
            elif chart_type == "box":
                df_chart = conn.execute(
                    f'SELECT CAST("{dim_col}" AS VARCHAR) AS group_col, '
                    f'CAST("{measure_col}" AS DOUBLE) AS val '
                    f'FROM "{active_tbl}" '
                    f'WHERE "{measure_col}" IS NOT NULL AND "{dim_col}" IS NOT NULL LIMIT 5000'
                ).df()
            else:
                if agg_func == "COUNT_DISTINCT":
                    agg_expr = f'COUNT(DISTINCT "{measure_col}")'
                elif agg_func == "COUNT":
                    agg_expr = "COUNT(*)"
                else:
                    agg_expr = f'{agg_func}(CAST("{measure_col}" AS DOUBLE))'
                df_chart = conn.execute(f"""
                    SELECT CAST("{dim_col}" AS VARCHAR) AS group_col,
                           {agg_expr} AS agg_val
                    FROM "{active_tbl}"
                    WHERE "{dim_col}" IS NOT NULL AND "{measure_col}" IS NOT NULL
                    GROUP BY 1 ORDER BY 2 DESC LIMIT {top_n}
                """).df()

            # ── Build figure ──────────────────────────────────────────────────
            lc = dict(template="plotly_white", height=chart_height,
                      margin=dict(l=10, r=10, t=40, b=10),
                      font=dict(family="Inter, sans-serif", size=11))

            if chart_type == "bar":
                fig_custom = px.bar(
                    df_chart, x="group_col", y="agg_val",
                    text_auto=(".3s" if show_labels else None),
                    color="group_col",
                    color_discrete_sequence=palette if isinstance(palette, list) else None,
                    labels={"group_col": dim_col, "agg_val": f"{agg_label}({measure_col})"},
                )
                if show_labels:
                    fig_custom.update_traces(textposition="outside")
            elif chart_type == "line":
                fig_custom = px.line(
                    df_chart, x="group_col", y="agg_val", markers=True,
                    labels={"group_col": dim_col, "agg_val": f"{agg_label}({measure_col})"},
                )
                if show_labels:
                    fig_custom.update_traces(
                        text=df_chart["agg_val"].apply(lambda v: f"{v:,.1f}"),
                        textposition="top center", mode="lines+markers+text",
                    )
            elif chart_type == "area":
                fig_custom = px.area(
                    df_chart, x="group_col", y="agg_val",
                    labels={"group_col": dim_col, "agg_val": f"{agg_label}({measure_col})"},
                )
            elif chart_type == "scatter":
                fig_custom = px.scatter(
                    df_chart, x="x_val", y="y_val", opacity=0.7,
                    labels={"x_val": dim_col, "y_val": measure_col},
                )
            elif chart_type == "pie":
                fig_custom = px.pie(
                    df_chart, names="group_col", values="agg_val", hole=0.4,
                    color_discrete_sequence=palette if isinstance(palette, list) else None,
                )
                if show_labels:
                    fig_custom.update_traces(textinfo="percent+label")
            elif chart_type == "box":
                fig_custom = px.box(
                    df_chart, x="group_col", y="val", color="group_col",
                    color_discrete_sequence=palette if isinstance(palette, list) else None,
                    labels={"group_col": dim_col, "val": measure_col},
                )
            elif chart_type == "histogram":
                fig_custom = px.histogram(df_chart, x="val", nbins=30,
                                          labels={"val": measure_col})
            elif chart_type == "heatmap":
                z_matrix = np.array(df_chart["agg_val"].tolist()).reshape(1, -1)
                fig_custom = go.Figure(go.Heatmap(
                    z=z_matrix, x=df_chart["group_col"].tolist(),
                    y=[f"{agg_label}({measure_col})"],
                    colorscale="Blues", showscale=True,
                ))

            if fig_custom:
                fig_custom.update_layout(**lc)
                fig_custom.update_layout(showlegend=(chart_type not in ("heatmap", "histogram")))

            # ── Render ── use st.container (NOT bare HTML divs) so widgets render correctly
            with st.container(border=True):
                st.markdown(
                    f"<div class='chart-card-title'>✦ {chart_type_label} · "
                    f"{agg_label}({measure_col}) by {dim_col}</div>",
                    unsafe_allow_html=True,
                )
                if fig_custom:
                    st.plotly_chart(fig_custom, width='stretch', key="custom_chart_main")
                    with st.expander("View underlying data", expanded=False):
                        st.dataframe(df_chart, width='stretch', height=200)
                    with st.expander("Export chart spec (JSON)", expanded=False):
                        spec = fig_custom.to_json()
                        st.code(spec[:2000] + ("..." if len(spec) > 2000 else ""), language="json")
                        st.download_button(
                            "Download full JSON spec", data=spec,
                            file_name=f"chart_{chart_type}_{measure_col}_{dim_col}.json",
                            mime="application/json", key="dl_chart_spec",
                        )
                else:
                    st.warning("Could not build figure for the selected parameters.")

            # Store for harness
            st.session_state["harness_df"] = df_chart
            st.session_state["harness_params"] = {
                "chart_type": chart_type, "measure_col": measure_col,
                "dim_col": dim_col, "agg_func": agg_func,
                "top_n": top_n,
                "row_count": len(df_chart) if df_chart is not None else 0,
            }

        except Exception as e:
            st.error(f"Chart generation error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – CHART TEST HARNESS
# ══════════════════════════════════════════════════════════════════════════════
with tab_harness:
    st.markdown("<div class='dash-section-header'>🧪 Chart Test Harness</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:12.5px;color:#64748b;margin-top:-6px;margin-bottom:16px;'>"
        "Automated assertions to validate the dataset, analytics engine, and custom charts.</p>",
        unsafe_allow_html=True,
    )

    hcol1, hcol2 = st.columns([2, 1], gap="medium")
    with hcol1:
        harness_suite = st.multiselect(
            "Select Test Suites to Run",
            ["📁 Dataset Validation", "📊 Analytics Engine",
             "🛠️ Custom Chart Builder", "🔢 KPI Integrity", "🔍 Outlier Detection"],
            default=["📁 Dataset Validation", "📊 Analytics Engine", "🔢 KPI Integrity"],
            key="harness_suites",
        )
    with hcol2:
        st.write("")
        st.write("")
        run_harness = st.button("▶  Run Tests", type="primary",
                                width='stretch', key="btn_harness")

    if run_harness or st.session_state.get("harness_ran"):
        st.session_state["harness_ran"] = True
        results = []

        def add_result(suite, name, passed, msg="", warn=False):
            results.append({"suite": suite, "name": name,
                            "passed": passed, "msg": msg, "warn": warn})

        conn_h = st.session_state.db.conn

        # Suite 1 – Dataset Validation
        if "📁 Dataset Validation" in harness_suite:
            sn = "📁 Dataset Validation"
            exists = st.session_state.db.table_exists(active_tbl)
            add_result(sn, "Table exists in DuckDB", exists,
                       f"Table '{active_tbl}' {'found' if exists else 'missing'}")
            try:
                rc = conn_h.execute(f'SELECT COUNT(*) FROM "{active_tbl}"').fetchone()[0]
                add_result(sn, "Row count > 0", rc > 0, f"{rc:,} rows loaded")
            except Exception as e:
                add_result(sn, "Row count > 0", False, str(e))
            add_result(sn, "Has numeric measure columns", len(measures) > 0,
                       f"Detected: {', '.join(measures[:5]) or 'None'}")
            try:
                null_cols = []
                for col in (measures + dimensions)[:10]:
                    nn = conn_h.execute(
                        f'SELECT COUNT(*) FROM "{active_tbl}" WHERE "{col}" IS NOT NULL'
                    ).fetchone()[0]
                    if nn == 0:
                        null_cols.append(col)
                add_result(sn, "No fully-null columns", len(null_cols) == 0,
                           f"All-null: {null_cols}" if null_cols else "All columns have data")
            except Exception as e:
                add_result(sn, "No fully-null columns", False, str(e), warn=True)
            add_result(sn, "Has categorical dimensions", len(dimensions) > 0,
                       f"Detected: {', '.join(dimensions[:5]) or 'None'}",
                       warn=(len(dimensions) == 0))

        # Suite 2 – Analytics Engine
        if "📊 Analytics Engine" in harness_suite:
            sn = "📊 Analytics Engine"
            add_result(sn, "Analytics engine returns has_data=True", dyn["has_data"],
                       "Dataset loaded and processed" if dyn["has_data"] else "No data")
            add_result(sn, "KPI list non-empty", len(dyn.get("kpis", [])) >= 1,
                       f"{len(dyn.get('kpis', []))} KPIs generated")
            add_result(sn, "Trend chart generated", dyn.get("trend_fig") is not None,
                       "trend_fig present" if dyn.get("trend_fig") else "trend_fig is None",
                       warn=dyn.get("trend_fig") is None)
            add_result(sn, "Category chart generated", dyn.get("cat_fig") is not None,
                       "cat_fig present" if dyn.get("cat_fig") else "cat_fig is None",
                       warn=dyn.get("cat_fig") is None)
            add_result(sn, "Radar/Outlier chart generated", dyn.get("radar_fig") is not None,
                       "radar_fig present" if dyn.get("radar_fig") else "radar_fig is None",
                       warn=dyn.get("radar_fig") is None)
            ins = dyn.get("insights", [])
            add_result(sn, "Auto-insights generated", len(ins) >= 1,
                       f"{len(ins)} insight(s) found")

        # Suite 3 – Custom Chart Builder
        if "🛠️ Custom Chart Builder" in harness_suite:
            sn = "🛠️ Custom Chart Builder"
            hp  = st.session_state.get("harness_params")
            hdf = st.session_state.get("harness_df")
            if hp is None:
                add_result(sn, "Custom chart was generated",
                           False, "Run a chart in the Builder tab first", warn=True)
            else:
                add_result(sn, "Chart DataFrame non-empty",
                           hdf is not None and len(hdf) > 0,
                           f"{hp['row_count']} rows in chart data")
                valid_types = list(CHART_TYPES.values())
                add_result(sn, "Chart type is valid",
                           hp["chart_type"] in valid_types,
                           f"Type: {hp['chart_type']}")
                try:
                    cols = conn_h.execute(f'SELECT * FROM "{active_tbl}" LIMIT 0').df().columns.tolist()
                    mc_ok = hp["measure_col"] in cols
                    add_result(sn, "Measure column exists in table", mc_ok,
                               f"Column '{hp['measure_col']}' {'found' if mc_ok else 'missing'}")
                except Exception as e:
                    add_result(sn, "Measure column exists", False, str(e))
                if hdf is not None:
                    nan_count = int(hdf.isnull().sum().sum())
                    add_result(sn, "Chart data has no NaN values",
                               nan_count == 0, f"{nan_count} NaN value(s)",
                               warn=(nan_count > 0))
                    within_n = hp["row_count"] <= hp.get("top_n", 30) + 1
                    add_result(sn, f"Row count within Top-N limit", within_n,
                               f"{hp['row_count']} rows (limit {hp.get('top_n', 30)})")

        # Suite 4 – KPI Integrity
        if "🔢 KPI Integrity" in harness_suite:
            sn = "🔢 KPI Integrity"
            kpis = dyn.get("kpis", [])
            add_result(sn, "Exactly 4 KPI cards", len(kpis) == 4,
                       f"{len(kpis)} KPI card(s) generated")
            for i, kpi in enumerate(kpis):
                val_ok = bool(kpi.get("val", ""))
                add_result(sn, f"KPI #{i+1} '{kpi['label']}' has a value",
                           val_ok, kpi.get("val", "(empty)"))
            if measures:
                try:
                    pm = measures[0]
                    sql_total = conn_h.execute(
                        f'SELECT SUM(CAST("{pm}" AS DOUBLE)) FROM "{active_tbl}"'
                    ).fetchone()[0]
                    add_result(sn, f"Primary measure '{pm}' SQL sum is non-negative",
                               (sql_total or 0) >= 0,
                               f"SQL SUM = {sql_total:,.2f}" if sql_total else "SUM = 0")
                except Exception as e:
                    add_result(sn, "Primary measure SQL sum", False, str(e), warn=True)

        # Suite 5 – Outlier Detection
        if "🔍 Outlier Detection" in harness_suite:
            sn = "🔍 Outlier Detection"
            for m in measures[:3]:
                try:
                    r = conn_h.execute(
                        f'SELECT AVG(CAST("{m}" AS DOUBLE)), STDDEV(CAST("{m}" AS DOUBLE)) '
                        f'FROM "{active_tbl}" WHERE "{m}" IS NOT NULL'
                    ).fetchone()
                    mean_v, std_v = (r[0] or 0), (r[1] or 0)
                    if std_v > 0:
                        out_cnt = conn_h.execute(
                            f'SELECT COUNT(*) FROM "{active_tbl}" '
                            f'WHERE ABS(CAST("{m}" AS DOUBLE) - {mean_v}) > 2 * {std_v}'
                        ).fetchone()[0]
                        rate = out_cnt / max(row_count, 1)
                        add_result(sn, f"'{m}' outlier rate < 15%",
                                   rate < 0.15, f"{out_cnt} outliers ({rate*100:.1f}%)",
                                   warn=(0.05 < rate < 0.15))
                    else:
                        add_result(sn, f"'{m}' std deviation", True,
                                   "Zero variance (constant column)", warn=True)
                except Exception as e:
                    add_result(sn, f"'{m}' outlier check", False, str(e), warn=True)

        # ── Summary metrics ─────────────────────────────────────────────────────
        total  = len(results)
        passed = sum(1 for r in results if r["passed"])
        warns  = sum(1 for r in results if r.get("warn") and r["passed"])
        failed = total - passed

        sc1, sc2, sc3, sc4 = st.columns(4, gap="medium")
        sc1.metric("Total Tests", total)
        sc2.metric("✅ Passed", passed)
        sc3.metric("⚠️ Warnings", warns)
        sc4.metric("❌ Failed", failed)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Per-suite results ───────────────────────────────────────────────────
        suites_seen = list(dict.fromkeys(r["suite"] for r in results))
        for suite in suites_seen:
            sr = [r for r in results if r["suite"] == suite]
            sp = sum(1 for r in sr if r["passed"])
            icon = "✅" if sp == len(sr) else ("⚠️" if sp > 0 else "❌")
            with st.expander(f"{icon} {suite} — {sp}/{len(sr)} passed", expanded=True):
                for r in sr:
                    if r["passed"] and not r.get("warn"):
                        cls, ico = "harness-result-pass", "✓"
                    elif r["passed"] and r.get("warn"):
                        cls, ico = "harness-result-warn", "⚠"
                    else:
                        cls, ico = "harness-result-fail", "✗"
                    st.markdown(
                        f"<div class='{cls}'><span style='font-size:14px;'>{ico}</span> "
                        f"<strong>{r['name']}</strong>"
                        f"{'  —  ' + r['msg'] if r['msg'] else ''}</div>",
                        unsafe_allow_html=True,
                    )

        # ── Export ──────────────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📤 Export test results (JSON)", expanded=False):
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "dataset": active_tbl,
                "summary": {"total": total, "passed": passed, "warnings": warns, "failed": failed},
                "results": results,
            }
            st.download_button(
                "⬇ Download test results",
                data=json.dumps(export_data, indent=2),
                file_name=f"harness_{active_tbl}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json", key="dl_harness_results",
            )
