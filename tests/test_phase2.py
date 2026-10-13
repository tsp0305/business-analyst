import pytest
from core.llm import MockLLM
from core.schemas import ToolCall, FinalAnswer
from phases.phase2_analysis import run_phase_2
from evals.generate_data import generate_sales_data
from core.db import DBContext
from core.tools import ToolRegistry
from tools import get_analytics_tools
import os

@pytest.fixture
def db_context(tmp_path):
    csv_path = str(tmp_path / "sales.csv")
    generate_sales_data(seed=42, output_csv=csv_path, output_truth=str(tmp_path / "truth.json"))
    db = DBContext()
    db.load_csv(csv_path, "sales")
    return db

def test_phase2_success(db_context, tmp_path):
    # Get exact numbers from the tool to pass the verifier
    registry = ToolRegistry()
    for t in get_analytics_tools(db_context): registry.register(t)
    real_res = registry.execute("trend_analysis", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": "region='South' AND prod_cat='Electronics'"}, ["trend_analysis"])
    
    mock = MockLLM([
        ToolCall(name="trend_analysis", args={"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": "region='South' AND prod_cat='Electronics'"}, thought="check trend"),
        FinalAnswer(payload={
            "summary": "Revenue dropped",
            "findings": [{"claim": "Revenue dropped last month", "numbers": [real_res.get("percent_change", -19.4)], "evidence_ids": ["E1"]}],
            "root_cause": "Unknown",
            "quantified_impact": "",
            "recommendation": "Investigate further",
            "caveats": []
        })
    ])
    
    question = "Why did revenue drop last month?"
    res = run_phase_2(mock, question, "sales", db_context, trace_dir=str(tmp_path))
    assert res["success"]
    assert res["verified"]
    assert "findings" in res["answer"]

def test_phase2_verify_failure_then_success(db_context, tmp_path):
    registry = ToolRegistry()
    for t in get_analytics_tools(db_context): registry.register(t)
    real_res = registry.execute("trend_analysis", {"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": "region='South' AND prod_cat='Electronics'"}, ["trend_analysis"])
    
    mock = MockLLM([
        ToolCall(name="trend_analysis", args={"table": "sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": "region='South' AND prod_cat='Electronics'"}, thought="check trend"),
        # Incorrect numbers
        FinalAnswer(payload={
            "summary": "Revenue dropped",
            "findings": [{"claim": "Revenue dropped last month", "numbers": [99999], "evidence_ids": ["E1"]}],
            "root_cause": "", "quantified_impact": "", "recommendation": "", "caveats": []
        }),
        # It gets nudge, fixes it
        FinalAnswer(payload={
            "summary": "Revenue dropped",
            "findings": [{"claim": "Revenue dropped last month", "numbers": [real_res.get("percent_change", -19.4)], "evidence_ids": ["E1"]}],
            "root_cause": "", "quantified_impact": "", "recommendation": "", "caveats": []
        })
    ])
    
    question = "Why did revenue drop last month?"
    res = run_phase_2(mock, question, "sales", db_context, trace_dir=str(tmp_path))
    assert res["success"]
    assert res["verified"]
