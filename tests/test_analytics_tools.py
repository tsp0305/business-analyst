import pytest
import pandas as pd
import json
import os
from core.db import DBContext
from core.tools import ToolRegistry
from tools import get_analytics_tools
from evals.generate_data import generate_sales_data

@pytest.fixture(scope="module")
def db_context(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("data")
    csv_path = str(tmp_path / "sample_sales.csv")
    truth_path = str(tmp_path / "ground_truth.json")
    
    # Generate data
    generate_sales_data(seed=42, output_csv=csv_path, output_truth=truth_path)
    
    db = DBContext()
    db.load_csv(csv_path, "sales")
    return db, csv_path, truth_path

@pytest.fixture
def registry(db_context):
    db, _, _ = db_context
    reg = ToolRegistry()
    for tool in get_analytics_tools(db):
        reg.register(tool)
    return reg

def test_run_sql(registry):
    # Blocks DROP
    res = registry.execute("run_sql", {"query": "DROP TABLE sales"}, ["run_sql"])
    assert "error" in res
    assert "blocked" in res["error"].lower() or "not ok" in res["error"].lower()
    
    # Allows SELECT
    res2 = registry.execute("run_sql", {"query": "SELECT COUNT(*) FROM sales"}, ["run_sql"])
    assert "error" not in res2
    assert isinstance(res2, list)

def test_compute_kpi(registry, db_context):
    _, csv_path, _ = db_context
    df = pd.read_csv(csv_path)
    expected_sum = df['rev_amt'].sum()
    
    res = registry.execute("compute_kpi", {"table": "sales", "kpi": "rev_amt", "aggregation": "sum", "filters": None}, ["compute_kpi"])
    assert "error" not in res
    assert abs(res["value"] - expected_sum) < 1

def test_trend_analysis(registry, db_context):
    _, _, truth_path = db_context
    with open(truth_path) as f:
        truth = json.load(f)
        
    res = registry.execute("trend_analysis", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": "region='South' AND prod_cat='Electronics'"}, ["trend_analysis"])
    assert "error" not in res
    assert res.get("percent_change") is not None
    assert abs(res["percent_change"] - truth["south_electronics_drop_pct"] * 100) < 5.0

def test_detect_anomalies(registry, db_context):
    _, _, truth_path = db_context
    with open(truth_path) as f:
        truth = json.load(f)
        
    res = registry.execute("detect_anomalies", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "method": "zscore"}, ["detect_anomalies"])
    assert "error" not in res
    anomalies = res["anomalies"]
    assert len(anomalies) >= 1
    assert any(truth["spike_date"] in str(a) for a in anomalies)

def test_drilldown(registry):
    res = registry.execute("drilldown_by_dimension", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "dimensions": ["region", "prod_cat"]}, ["drilldown_by_dimension"])
    assert "error" not in res
    assert len(res["changes"]) > 0
    assert any(c["dimension_values"].get("region") == "South" and c["dimension_values"].get("prod_cat") == "Electronics" for c in res["changes"])

def test_forecast(registry):
    res = registry.execute("forecast", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "horizon": 7, "grain": "day"}, ["forecast"])
    assert "error" not in res
    assert "forecast" in res
    assert len(res["forecast"]) == 7
    assert "intervals" in res
    
    # Error observation on short series
    res2 = registry.execute("forecast", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "horizon": 7, "grain": "year"}, ["forecast"])
    assert "error" in res2
    assert "series too short" in res2["error"].lower() or "not enough data" in res2["error"].lower()

def test_make_chart(registry):
    res = registry.execute("make_chart", {"chart_type": "bar", "data": [{"x": "A", "y": 10}], "x_col": "x", "y_col": "y", "title": "Test"}, ["make_chart"])
    assert "error" not in res
    assert "chart_id" in res
    assert os.path.exists(f"data/charts/{res['chart_id']}.json")

def test_bad_args(registry):
    res = registry.execute("compute_kpi", {"table": "sales", "kpi": "bad_col", "aggregation": "sum", "filters": None}, ["compute_kpi"])
    assert "error" in res
