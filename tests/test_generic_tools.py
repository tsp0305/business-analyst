import pytest
import pandas as pd
from core.db import DBContext
from core.tools import ToolRegistry
from tools import get_analytics_tools
from tools.base_tool import FilterCondition

@pytest.fixture(scope="module")
def multi_schema_db(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("generic_tools_data")
    
    # Dataset 1: Employees HR data
    # Columns: emp_id, department, role, salary, hire_date
    dates_emp = pd.date_range("2023-01-01", periods=180, freq="D").strftime("%Y-%m-%d").tolist()
    emp_data = []
    for i, dt in enumerate(dates_emp):
        dept = ["Engineering", "Sales", "Support", "Marketing"][i % 4]
        role = f"Role_{i % 3}"
        salary = 50000 + (i * 200) + (10000 if dept == "Engineering" else 0)
        emp_data.append({
            "emp_id": f"E{1000+i}",
            "department": dept,
            "role": role,
            "salary": salary,
            "hire_date": dt
        })
    df_emp = pd.DataFrame(emp_data)
    emp_csv = str(tmp_path / "employees.csv")
    df_emp.to_csv(emp_csv, index=False)

    # Dataset 2: Sensor / IoT fleet data
    # Columns: device_id, location, status, temperature, recorded_at
    dates_sensor = pd.date_range("2024-01-01", periods=120, freq="D").strftime("%Y-%m-%d").tolist()
    sensor_data = []
    for i, dt in enumerate(dates_sensor):
        loc = ["Warehouse_A", "Warehouse_B", "Factory_1"][i % 3]
        status = "Active" if i % 5 != 0 else "Idle"
        # Introduce an anomaly at index 60
        temp = 22.5 + (i * 0.05) if i != 60 else 98.4
        sensor_data.append({
            "device_id": f"DEV_{i % 10}",
            "location": loc,
            "status": status,
            "temperature": temp,
            "recorded_at": dt
        })
    df_sensor = pd.DataFrame(sensor_data)
    sensor_csv = str(tmp_path / "sensors.csv")
    df_sensor.to_csv(sensor_csv, index=False)

    db = DBContext()
    db.load_csv(emp_csv, "clean_employees")
    db.load_csv(sensor_csv, "clean_sensors")
    return db, df_emp, df_sensor

@pytest.fixture
def registry(multi_schema_db):
    db, _, _ = multi_schema_db
    reg = ToolRegistry()
    for tool in get_analytics_tools(db):
        reg.register(tool)
    return reg

# ----------------- KPI Tool Tests across 2 Schemas -----------------

def test_kpi_tool_employees_schema(registry, multi_schema_db):
    _, df_emp, _ = multi_schema_db
    # Test sum aggregation
    res_sum = registry.execute("compute_kpi", {
        "table": "clean_employees",
        "kpi": "salary",
        "aggregation": "sum"
    }, ["compute_kpi"])
    assert "error" not in res_sum
    assert abs(res_sum["value"] - df_emp["salary"].sum()) < 1.0

    # Test avg aggregation with structured filter
    res_avg = registry.execute("compute_kpi", {
        "table": "clean_employees",
        "kpi": "salary",
        "aggregation": "avg",
        "filters": [{"column": "department", "op": "=", "value": "Engineering"}]
    }, ["compute_kpi"])
    assert "error" not in res_avg
    eng_sal_avg = df_emp[df_emp["department"] == "Engineering"]["salary"].mean()
    assert abs(res_avg["value"] - eng_sal_avg) < 1.0

    # Test count aggregation
    res_count = registry.execute("compute_kpi", {
        "table": "clean_employees",
        "kpi": "emp_id",
        "aggregation": "count"
    }, ["compute_kpi"])
    assert "error" not in res_count
    assert res_count["value"] == len(df_emp)

def test_kpi_tool_sensors_schema(registry, multi_schema_db):
    _, _, df_sensor = multi_schema_db
    # Test max aggregation
    res_max = registry.execute("compute_kpi", {
        "table": "clean_sensors",
        "kpi": "temperature",
        "aggregation": "max"
    }, ["compute_kpi"])
    assert "error" not in res_max
    assert abs(res_max["value"] - 98.4) < 0.1

    # Test min aggregation with string filter
    res_min = registry.execute("compute_kpi", {
        "table": "clean_sensors",
        "kpi": "temperature",
        "aggregation": "min",
        "filters": "status = 'Active'"
    }, ["compute_kpi"])
    assert "error" not in res_min
    expected_min = df_sensor[df_sensor["status"] == "Active"]["temperature"].min()
    assert abs(res_min["value"] - expected_min) < 0.1

# ----------------- Trend Tool Tests across 2 Schemas -----------------

def test_trend_tool_employees_schema(registry):
    res = registry.execute("trend_analysis", {
        "table": "clean_employees",
        "metric": "salary",
        "date_column": "hire_date",
        "grain": "month",
        "aggregation": "sum"
    }, ["trend_analysis"])
    assert "error" not in res
    assert "percent_change" in res
    assert "last_period" in res
    assert "prior_period" in res
    assert res["last_period"] > 0

def test_trend_tool_sensors_schema(registry):
    res = registry.execute("trend_analysis", {
        "table": "clean_sensors",
        "metric": "temperature",
        "date_column": "recorded_at",
        "grain": "week",
        "aggregation": "avg"
    }, ["trend_analysis"])
    assert "error" not in res
    assert "percent_change" in res
    assert "last_period" in res
    assert res["prior_period"] > 0

# ----------------- Drilldown Tool Tests across 2 Schemas -----------------

def test_drilldown_tool_employees_schema(registry):
    res = registry.execute("drilldown_by_dimension", {
        "table": "clean_employees",
        "metric": "salary",
        "date_column": "hire_date",
        "dimensions": ["department", "role"],
        "aggregation": "avg"
    }, ["drilldown_by_dimension"])
    assert "error" not in res
    assert len(res["changes"]) > 0
    # Every change should have dimension_values with department and role
    first_change = res["changes"][0]
    assert "department" in first_change["dimension_values"]
    assert "role" in first_change["dimension_values"]

def test_drilldown_tool_sensors_schema(registry):
    res = registry.execute("drilldown_by_dimension", {
        "table": "clean_sensors",
        "metric": "temperature",
        "date_column": "recorded_at",
        "dimensions": ["location", "status"],
        "aggregation": "max"
    }, ["drilldown_by_dimension"])
    assert "error" not in res
    assert len(res["changes"]) > 0
    assert any("Warehouse_A" in str(c["dimension_values"]) for c in res["changes"])

# ----------------- Anomaly Tool Tests across 2 Schemas -----------------

def test_anomaly_tool_employees_schema(registry):
    res = registry.execute("detect_anomalies", {
        "table": "clean_employees",
        "metric": "salary",
        "date_column": "hire_date",
        "grain": "month",
        "method": "iqr"
    }, ["detect_anomalies"])
    assert "error" not in res
    assert "anomalies" in res

def test_anomaly_tool_sensors_schema(registry):
    res = registry.execute("detect_anomalies", {
        "table": "clean_sensors",
        "metric": "temperature",
        "date_column": "recorded_at",
        "grain": "day",
        "method": "zscore"
    }, ["detect_anomalies"])
    assert "error" not in res
    assert len(res["anomalies"]) >= 1
    # Check that day 60 anomaly was caught (index 60 corresponds to ~March 2024)
    spike_found = any("2024-03" in str(a) for a in res["anomalies"])
    assert spike_found

# ----------------- Forecast Tool Tests across 2 Schemas -----------------

def test_forecast_tool_employees_schema(registry):
    res = registry.execute("forecast", {
        "table": "clean_employees",
        "metric": "salary",
        "date_column": "hire_date",
        "horizon": 14,
        "grain": "day",
        "aggregation": "sum"
    }, ["forecast"])
    assert "error" not in res
    assert len(res["forecast"]) == 14
    assert "intervals" in res
    assert len(res["intervals"]) == 14

def test_forecast_tool_sensors_schema(registry):
    res = registry.execute("forecast", {
        "table": "clean_sensors",
        "metric": "temperature",
        "date_column": "recorded_at",
        "horizon": 5,
        "grain": "day",
        "aggregation": "avg"
    }, ["forecast"])
    assert "error" not in res
    assert len(res["forecast"]) == 5

# ----------------- Validation & Error Handling -----------------

def test_tool_invalid_identifiers(registry):
    # Invalid table
    res_bad_tbl = registry.execute("compute_kpi", {
        "table": "nonexistent_table",
        "kpi": "salary"
    }, ["compute_kpi"])
    assert "error" in res_bad_tbl

    # Invalid column
    res_bad_col = registry.execute("compute_kpi", {
        "table": "clean_employees",
        "kpi": "nonexistent_column"
    }, ["compute_kpi"])
    assert "error" in res_bad_col

    # SQL injection in table name
    res_inject = registry.execute("compute_kpi", {
        "table": "clean_employees; DROP TABLE clean_employees;",
        "kpi": "salary"
    }, ["compute_kpi"])
    assert "error" in res_inject
