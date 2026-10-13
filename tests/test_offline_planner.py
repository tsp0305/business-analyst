import pytest
import pandas as pd
from core.db import DBContext
from phases.planner import run_offline_planner

@pytest.fixture
def planner_db(tmp_path):
    # Create inventory data: item_id, warehouse, restock_date, stock_quantity, cost
    dates = pd.date_range("2023-01-01", periods=90, freq="D").strftime("%Y-%m-%d").tolist()
    data = []
    for i, d in enumerate(dates):
        wh = ["East_Hub", "West_Hub", "Central_Hub"][i % 3]
        qty = 100 + i * 5 if i != 40 else 950 # Anomaly at day 40
        data.append({
            "item_id": f"ITEM_{100+i}",
            "warehouse": wh,
            "restock_date": d,
            "stock_quantity": qty,
            "unit_cost": 15.5
        })
    df = pd.DataFrame(data)
    csv_path = str(tmp_path / "inventory.csv")
    df.to_csv(csv_path, index=False)

    db = DBContext()
    db.load_csv(csv_path, "clean_inventory")
    return db

def test_planner_general_overview(planner_db):
    res = run_offline_planner("Give me an overview of this inventory dataset", "clean_inventory", planner_db)
    assert res["verified"]
    assert "clean_inventory" in res["summary"]
    assert len(res["findings"]) >= 1

def test_planner_trend_query(planner_db):
    res = run_offline_planner("Show me the monthly stock_quantity trend", "clean_inventory", planner_db)
    assert res["verified"]
    assert "stock_quantity" in res["summary"]
    assert res["chart"] is not None
    assert len(res["findings"]) >= 1

def test_planner_anomaly_query(planner_db):
    res = run_offline_planner("Detect any spikes or anomalies in stock_quantity", "clean_inventory", planner_db)
    assert res["verified"]
    assert "anomal" in res["summary"].lower() or "outlier" in res["summary"].lower()
    assert res["chart"] is not None

def test_planner_breakdown_query(planner_db):
    res = run_offline_planner("Break down stock_quantity by warehouse", "clean_inventory", planner_db)
    assert res["verified"]
    assert "warehouse" in res["summary"].lower()
    assert res["chart"] is not None

def test_planner_missing_table(planner_db):
    res = run_offline_planner("Analyze trends", "non_existent_table", planner_db)
    assert "not found" in res["summary"].lower()
