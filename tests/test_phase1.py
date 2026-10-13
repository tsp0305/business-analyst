import pytest
from core.llm import MockLLM
from core.schemas import ToolCall, FinalAnswer
from phases.phase1_etl import run_phase_1
import pandas as pd
import os
from evals.generate_data import generate_sales_data

@pytest.fixture
def sample_data(tmp_path):
    csv_path = str(tmp_path / "sales.csv")
    generate_sales_data(seed=42, output_csv=csv_path, output_truth=str(tmp_path / "truth.json"))
    return csv_path

def test_phase1_success(sample_data, tmp_path):
    out_table = "cleaned_sales"
    # The python code will load the CSV, do something, and create a table in duckdb.
    # We will mock the LLM to write some duckdb/pandas code.
    code_pass = f"""
import duckdb
import pandas as pd
df = pd.read_csv('{sample_data}')
# deduplicate by order_id keeping the latest load_timestamp
df = df.sort_values('load_timestamp').drop_duplicates('order_id', keep='last')
db.conn.execute("CREATE TABLE {out_table} AS SELECT * FROM df")
print("Row count:", len(df))
"""

    mock = MockLLM([
        ToolCall(name="run_python", args={"code": code_pass}, thought="writing code"),
        FinalAnswer(payload={"table_name": out_table, "row_count": 365}) # whatever length it returns
    ])
    
    res = run_phase_1(mock, sample_data, out_table, trace_dir=str(tmp_path))
    assert res["success"]
    assert res["table_name"] == out_table
    assert res["row_count"] > 0

def test_phase1_retry(sample_data, tmp_path):
    out_table = "cleaned_sales_2"
    code_fail = "print(1/0)"
    code_pass = f"""
import pandas as pd
df = pd.read_csv('{sample_data}')
db.conn.execute("CREATE TABLE {out_table} AS SELECT * FROM df")
"""
    mock = MockLLM([
        ToolCall(name="run_python", args={"code": code_fail}, thought="will fail"),
        ToolCall(name="run_python", args={"code": code_pass}, thought="will pass"),
        FinalAnswer(payload={"table_name": out_table, "row_count": 100})
    ])
    
    res = run_phase_1(mock, sample_data, out_table, trace_dir=str(tmp_path))
    assert res["success"]
    assert res["table_name"] == out_table
