import pytest
from core.llm import MockLLM
from core.schemas import ToolCall, AskUser, FinalAnswer
from phases.phase2_analysis import run_phase_2
from core.db import DBContext
from core.profiler import clean_and_profile_dataset

@pytest.fixture
def multi_ds_db(tmp_path):
    db = DBContext(db_path=str(tmp_path / "multi_grounding.duckdb"))
    
    # Dataset 1: employees
    db.conn.execute("CREATE TABLE ds_employees (emp_id INT, emp_name VARCHAR, salary DOUBLE)")
    db.conn.execute("INSERT INTO ds_employees VALUES (1, 'Alice', 95000), (2, 'Bob', 82000)")
    clean_and_profile_dataset(db, "ds_employees")

    # Dataset 2: orders
    db.conn.execute("CREATE TABLE ds_orders (order_num INT, customer VARCHAR, total_amt DOUBLE)")
    db.conn.execute("INSERT INTO ds_orders VALUES (101, 'Acme', 500.0), (102, 'Beta', 1200.0)")
    clean_and_profile_dataset(db, "ds_orders")

    yield db
    db.close()

def test_catalog_and_tool_schemas_in_prompt(multi_ds_db, tmp_path):
    received_prompts = []

    class InspectPromptLLM(MockLLM):
        def next_action(self, messages: list, tools: list):
            received_prompts.append(messages[0]["content"])
            return FinalAnswer(payload={
                "summary": "Completed prompt inspection",
                "findings": [{"claim": "Inspected", "numbers": [], "evidence_ids": []}],
                "root_cause": "", "quantified_impact": "", "recommendation": "", "caveats": []
            })

    mock_llm = InspectPromptLLM(script=[])
    res = run_phase_2(mock_llm, "What is the average salary?", "clean_employees", multi_ds_db, trace_dir=str(tmp_path))
    assert res["success"]

    # Verify catalog content in the prompt
    sys_prompt = received_prompts[0]
    assert "Dataset Catalog:" in sys_prompt
    assert "clean_employees" in sys_prompt
    assert "clean_orders" in sys_prompt
    assert "salary" in sys_prompt

    # Verify tool argument schemas in the prompt
    assert "Available Tool Schemas:" in sys_prompt
    assert "compute_kpi" in sys_prompt
    assert "run_sql" in sys_prompt

def test_no_silent_fallback_surfaces_failure(multi_ds_db, tmp_path):
    # LLM that fails or runs out of steps without valid findings
    failing_llm = MockLLM(script=[
        ToolCall(name="unknown_tool", args={}, thought="trying non-existent tool")
    ])

    res = run_phase_2(failing_llm, "Do something", "clean_employees", multi_ds_db, trace_dir=str(tmp_path))
    # Must fail cleanly and surface error, NOT fall back to direct_analyst!
    assert not res["success"]
    assert "Analysis failed" in res["error"]
    assert not res["verified"]

def test_ask_user_for_dataset_disambiguation(multi_ds_db, tmp_path):
    mock_llm = MockLLM(script=[
        AskUser(question="Did you mean employees salary or orders total_amt?", options=["employees", "orders"])
    ])

    res = run_phase_2(mock_llm, "What are total sales?", "clean_orders", multi_ds_db, trace_dir=str(tmp_path))
    assert not res["success"]
    assert res["stop_reason"] == "user_input_needed"
    assert "Clarification" in res["error"]
    assert res["state_file"] is not None
