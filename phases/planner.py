import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any, Optional, List
from core.evidence import EvidenceLedger
from core.tools import ToolRegistry
from tools import get_analytics_tools
from core.profiler import profile_table
from core.verifier import verify_answer

def run_offline_planner(query: str, table_name: str, db, catalog: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Schema-driven, zero-cost / offline BI analysis engine.
    Executes generic analytics tools via ToolRegistry and EvidenceLedger,
    creates dynamic interactive charts, and verifies findings.
    Works on ANY tabular schema without hardcoded column names.
    """
    conn = db.conn
    ledger = EvidenceLedger()
    registry = ToolRegistry()
    for tool in get_analytics_tools(db):
        registry.register(tool)

    schema = db.get_schema()
    real_tables = {k.lower(): k for k in schema}
    if table_name.lower() not in real_tables:
        return {
            "summary": f"Table '{table_name}' not found in active database.",
            "root_cause": "The requested table does not exist in DuckDB.",
            "quantified_impact": "0 rows available for analysis.",
            "recommendation": "Ingest a dataset using the sidebar to begin analysis.",
            "findings": [],
            "chart": None,
            "evidence_ids": [],
            "verified": True
        }

    actual_table = real_tables[table_name.lower()]

    # Profile table to dynamically discover column roles
    profile = profile_table(conn, actual_table)
    roles = profile.get("roles", {})
    measures = roles.get("measure", [])
    dates = roles.get("date", [])
    dimensions = roles.get("dimension", [])
    ids = roles.get("id", [])
    row_count = profile.get("row_count", 0)

    # Record profile in ledger
    eid_prof = ledger.add(
        "profile_table",
        {"table": actual_table},
        {"row_count": float(row_count), "col_count": float(len(profile.get("columns", {})))}
    )

    q_lower = query.lower()

    # Pick primary columns
    primary_measure = measures[0] if measures else None
    primary_date = dates[0] if dates else None
    primary_dim = dimensions[0] if dimensions else None

    # Check if user mentioned specific columns
    for m in measures:
        if m.lower() in q_lower:
            primary_measure = m
            break
    for d in dates:
        if d.lower() in q_lower:
            primary_date = d
            break
    for dim in dimensions:
        if dim.lower() in q_lower:
            primary_dim = dim
            break

    fig = None
    findings = []
    summary = ""
    root_cause = ""
    quantified_impact = ""
    recommendation = ""

    # 1. DATA QUALITY & CLEANING INTENT
    if any(k in q_lower for k in ["clean", "transform", "duplicat", "prep", "etl", "null", "schema", "quality"]):
        findings.append({
            "claim": f"Active table '{actual_table}' contains {row_count} validated records across {len(profile.get('columns', {}))} columns.",
            "numbers": [float(row_count), float(len(profile.get('columns', {})))],
            "evidence_ids": [eid_prof]
        })

        summary = f"Data Profiling & Quality Audit for '{actual_table}'"
        root_cause = f"Identified {len(measures)} measures, {len(dates)} dates, and {len(dimensions)} dimensions."
        quantified_impact = f"Verified {row_count} rows across {len(profile.get('columns', {}))} fields."
        recommendation = "Maintain automated schema validation and column role tagging upon ingestion."

    # 2. ANOMALY DETECTION INTENT
    elif any(k in q_lower for k in ["anomal", "spike", "outlier", "unusual", "irregular"]) and primary_measure and primary_date:
        anom_res = registry.execute("detect_anomalies", {
            "table": actual_table,
            "metric": primary_measure,
            "date_column": primary_date,
            "method": "zscore",
            "grain": "day"
        }, ["detect_anomalies"])

        eid1 = ledger.add("detect_anomalies", {"metric": primary_measure}, anom_res)
        anomalies = anom_res.get("anomalies", [])
        anom_count = float(len(anomalies))

        # Fetch daily data for chart
        df_daily = conn.execute(f"""
            SELECT CAST("{primary_date}" AS VARCHAR) as dt, SUM("{primary_measure}") as val
            FROM "{actual_table}"
            GROUP BY 1
            ORDER BY 1
        """).df()

        fig = px.line(df_daily, x="dt", y="val", title=f"Daily {primary_measure} Anomaly Detection ({actual_table})")
        fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))

        if anomalies:
            anom_pts = df_daily[df_daily["dt"].astype(str).isin([str(a) for a in anomalies])]
            if not anom_pts.empty:
                fig.add_trace(go.Scatter(
                    x=anom_pts["dt"],
                    y=anom_pts["val"],
                    mode="markers+text",
                    name="Anomaly",
                    marker=dict(color="red", size=12, symbol="diamond")
                ))

            findings.append({
                "claim": f"Detected {int(anom_count)} statistical anomalies in '{primary_measure}' using Z-score filtering.",
                "numbers": [anom_count],
                "evidence_ids": [eid1]
            })
            summary = f"Detected {int(anom_count)} statistical outlier periods in '{primary_measure}'."
            root_cause = "Metric values exceeded standard statistical distribution bounds."
            quantified_impact = f"Total of {int(anom_count)} outlier periods identified."
            recommendation = "Investigate external drivers or unusual batch transactions during flagged dates."
        else:
            findings.append({
                "claim": f"No statistical anomalies detected in '{primary_measure}'.",
                "numbers": [0.0],
                "evidence_ids": [eid1]
            })
            summary = f"No statistical outliers detected in '{primary_measure}'."
            root_cause = "Metric values remained within standard statistical bounds across all recorded periods."
            quantified_impact = "Zero significant outlier anomalies detected."
            recommendation = "Continue standard operational monitoring across temporal grain."

    # 3. TREND & PERIOD COMPARISON INTENT
    elif any(k in q_lower for k in ["trend", "drop", "why", "decrease", "growth", "month", "timeline", "progression"]) and primary_measure and primary_date:
        trend_res = registry.execute("trend_analysis", {
            "table": actual_table,
            "metric": primary_measure,
            "date_column": primary_date,
            "grain": "month",
            "aggregation": "sum"
        }, ["trend_analysis"])

        eid1 = ledger.add("trend_analysis", {"metric": primary_measure}, trend_res)
        pct = float(trend_res.get("percent_change", 0.0))
        last_val = float(trend_res.get("last_period", 0.0))
        prior_val = float(trend_res.get("prior_period", 0.0))
        diff_val = float(trend_res.get("diff", last_val - prior_val))

        # Plot trend
        df_monthly = conn.execute(f"""
            SELECT strftime('%Y-%m', CAST("{primary_date}" AS DATE)) as period, SUM("{primary_measure}") as val
            FROM "{actual_table}"
            GROUP BY 1
            ORDER BY 1
        """).df()

        fig = px.line(df_monthly, x="period", y="val", markers=True, title=f"Monthly {primary_measure} Trend ({actual_table})")
        fig.update_traces(line_color="#2563EB", line_width=3)
        fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))

        findings.append({
            "claim": f"Recent period {primary_measure} shifted to {last_val} from prior {prior_val} with {pct}% change.",
            "numbers": [last_val, prior_val, pct],
            "evidence_ids": [eid1]
        })
        findings.append({
            "claim": f"Net period difference in {primary_measure} is {diff_val}.",
            "numbers": [diff_val],
            "evidence_ids": [eid1]
        })

        summary = f"Monthly {primary_measure} analysis indicates {pct}% change in the most recent period."
        root_cause = "Period-over-period metric variance between recent and prior intervals."
        quantified_impact = f"Net period shift of {diff_val} in '{primary_measure}'."
        recommendation = "Monitor underlying dimensional contributions to sustain gains or address declines."

    # 4. DIMENSIONAL BREAKDOWN INTENT
    elif any(k in q_lower for k in ["breakdown", "category", "dimension", "segment", "distribution", "by ", "rank"]) and primary_dim and primary_measure:
        dim_query = f'SELECT "{primary_dim}", SUM("{primary_measure}") as total_val FROM "{actual_table}" GROUP BY 1 ORDER BY 2 DESC LIMIT 15'
        rows = conn.execute(dim_query).fetchall()
        top_name = str(rows[0][0]) if rows else "N/A"
        top_val = float(rows[0][1]) if rows else 0.0

        eid1 = ledger.add("run_sql", {"query": dim_query}, {"top_segment": top_name, "top_val": top_val})

        df_dim = pd.DataFrame(rows, columns=[primary_dim, "total_val"])
        fig = px.bar(df_dim, x=primary_dim, y="total_val", color=primary_dim, title=f"{primary_measure} by {primary_dim} ({actual_table})")
        fig.update_layout(template="plotly_white", showlegend=False, margin=dict(l=20, r=20, t=40, b=20))

        findings.append({
            "claim": f"Leading segment for '{primary_dim}' is '{top_name}' with {top_val} total {primary_measure}.",
            "numbers": [top_val],
            "evidence_ids": [eid1]
        })

        summary = f"Categorical breakdown of '{primary_measure}' across '{primary_dim}' for '{actual_table}'."
        root_cause = f"Segment '{top_name}' represents the largest volume of {primary_measure}."
        quantified_impact = f"Top segment accounts for {top_val} in '{primary_measure}'."
        recommendation = f"Focus operational optimization on top performing '{primary_dim}' segments."

    # 5. GENERAL OVERVIEW
    else:
        kpi_args = {"table": actual_table, "kpi": primary_measure or "1", "aggregation": "sum" if primary_measure else "count"}
        kpi_res = registry.execute("compute_kpi", kpi_args, ["compute_kpi"])
        eid1 = ledger.add("compute_kpi", kpi_args, kpi_res)
        val = float(kpi_res.get("value", row_count))

        findings.append({
            "claim": f"Total calculated {kpi_args['aggregation']} for '{actual_table}' is {val}.",
            "numbers": [val],
            "evidence_ids": [eid1]
        })

        summary = f"General Overview for '{actual_table}'"
        root_cause = f"Profiled {row_count} records across {len(profile.get('columns', {}))} fields."
        quantified_impact = f"Aggregate metric value is {val}."
        recommendation = "Query specific dimensions or time series for targeted insights."

    answer = {
        "summary": summary,
        "root_cause": root_cause,
        "quantified_impact": quantified_impact,
        "recommendation": recommendation,
        "findings": findings,
        "chart": fig,
        "evidence_ids": [eid for eid in ledger.evidence.keys()]
    }

    v_res = verify_answer(answer, ledger)
    answer["verified"] = v_res.get("verified", True)

    return answer

