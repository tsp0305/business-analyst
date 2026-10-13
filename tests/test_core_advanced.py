import pytest
import time
import json
import os
from core.schemas import ToolCall, AskUser, FinalAnswer
from core.llm import MockLLM
from core.evidence import EvidenceLedger
from core.guards import check_guards
from core.verifier import verify_answer
from core.context import ContextManager
from core.trace import Tracer
from core.hitl import pause_for_user, resume_from_user
from core.agent_loop import RunController, RunBudget
from core.tools import ToolRegistry, Tool
from pydantic import BaseModel
import tempfile

class DummyArgs(BaseModel):
    query: str

def dummy_tool_func(args):
    return {"result": f"Answer for {args['query']}", "nums": [100, 20]}

@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(Tool(name="dummy", description="Dummy", args_schema=DummyArgs, func=dummy_tool_func))
    return reg

# --- Evidence Tests ---
def test_evidence_ledger():
    ledger = EvidenceLedger()
    eid = ledger.add("dummy", {"query": "x"}, {"result": "y"})
    assert eid == "E1"
    assert ledger.get("E1")["tool"] == "dummy"
    
    index = ledger.get_index()
    assert "E1: dummy" in index

# --- Guards Tests ---
def test_loop_guards():
    # repeat -> nudge -> forced finalize
    history = [
        {"tool": "dummy", "args": {"q":"1"}, "result_summary": "res1"},
        {"tool": "dummy", "args": {"q":"1"}, "result_summary": "res1"}
    ]
    assert "repeat" in check_guards(history).lower()
    
    history.append({"tool": "dummy", "args": {"q":"1"}, "result_summary": "res1"})
    assert check_guards(history) == "FORCE_FINAL"

    # no new evidence for 3 steps
    history_no_ev = [
        {"tool": "dummy", "args": {"q":"a"}, "error": "err"},
        {"tool": "dummy", "args": {"q":"b"}, "error": "err"},
        {"tool": "dummy", "args": {"q":"c"}, "error": "err"}
    ]
    assert "no new evidence" in check_guards(history_no_ev).lower()

    history_no_ev.append({"tool": "dummy", "args": {"q":"d"}, "error": "err"})
    assert check_guards(history_no_ev) == "FORCE_FINAL"

    # A-B-A-B oscillation
    history_osc = [
        {"tool": "dummy", "args": {"q":"A"}, "result_summary": "1"},
        {"tool": "dummy", "args": {"q":"B"}, "result_summary": "2"},
        {"tool": "dummy", "args": {"q":"A"}, "result_summary": "1"},
        {"tool": "dummy", "args": {"q":"B"}, "result_summary": "2"}
    ]
    assert "oscillation" in check_guards(history_osc).lower()

# --- Verifier Tests ---
def test_verifier_pass():
    ledger = EvidenceLedger()
    ledger.add("dummy", {}, {"val": 100, "val2": 20}) # E1
    
    # 120 is derivable (100+20), 5 is ratio (100/20), 80 is percent diff or sub
    ans = {
        "summary": "ok",
        "findings": [{"claim": "x", "numbers": [100, 120, 5], "evidence_ids": ["E1"]}],
        "root_cause": "", "quantified_impact": "", "recommendation": "", "caveats": []
    }
    res = verify_answer(ans, ledger)
    assert res["verified"]

def test_verifier_fail_fabricated():
    ledger = EvidenceLedger()
    ledger.add("dummy", {}, {"val": 10}) # E1
    ans = {
        "findings": [{"claim": "x", "numbers": [999], "evidence_ids": ["E1"]}]
    }
    res = verify_answer(ans, ledger)
    assert not res["verified"]
    assert "999" in res["errors"][0]

def test_verifier_missing_evidence():
    ledger = EvidenceLedger()
    ans = {
        "findings": [{"claim": "x", "numbers": [10], "evidence_ids": ["E99"]}]
    }
    res = verify_answer(ans, ledger)
    assert not res["verified"]
    assert "E99" in res["errors"][0]

# --- Agent Loop Tests ---
def test_agent_loop_happy(registry, tmp_path):
    mock = MockLLM([
        ToolCall(name="dummy", args={"query": "test"}, thought="thinking"),
        FinalAnswer(payload={"summary": "done", "findings": [{"claim":"x", "numbers":[100], "evidence_ids":["E1"]}], "root_cause": "", "quantified_impact": "", "recommendation": "", "caveats": []})
    ])
    ctx = ContextManager("sys", {}, {})
    tracer = Tracer(run_id="run1", trace_dir=str(tmp_path))
    ctrl = RunController(ctx, registry, ["dummy"], RunBudget(), tracer, mock)
    
    res = ctrl.run()
    assert res.stop_reason == "final"
    assert res.verified
    assert len(ctrl.ledger.get_index()) > 0
    assert "run1.jsonl" in os.listdir(tmp_path)

def test_agent_loop_budgets(registry, tmp_path):
    mock = MockLLM([ToolCall(name="dummy", args={"query": "test"}, thought="t")] * 5)
    ctx = ContextManager("sys", {}, {})
    tracer = Tracer(run_id="run2", trace_dir=str(tmp_path))
    ctrl = RunController(ctx, registry, ["dummy"], RunBudget(max_steps=2), tracer, mock)
    
    res = ctrl.run()
    assert res.stop_reason == "budget_exhausted"

def test_agent_loop_hitl_pause_resume(registry, tmp_path):
    mock = MockLLM([
        AskUser(question="What?"),
        FinalAnswer(payload={"msg": "res"})
    ])
    ctx = ContextManager("sys", {}, {})
    tracer = Tracer(run_id="run3", trace_dir=str(tmp_path))
    ctrl = RunController(ctx, registry, ["dummy"], RunBudget(), tracer, mock)
    
    res = ctrl.run()
    assert res.stop_reason == "user_input_needed"
    
    # simulate user reply
    state_file = pause_for_user(ctrl, "run3", str(tmp_path))
    ctrl2 = resume_from_user(state_file, "User says Hello", mock, registry, tracer)
    res2 = ctrl2.run()
    assert res2.stop_reason == "final"

def test_agent_loop_disallowed_tool(registry, tmp_path):
    mock = MockLLM([
        ToolCall(name="unknown", args={}, thought="t"),
        FinalAnswer(payload={"msg": "res"})
    ])
    ctx = ContextManager("sys", {}, {})
    tracer = Tracer(run_id="run4", trace_dir=str(tmp_path))
    ctrl = RunController(ctx, registry, ["dummy"], RunBudget(), tracer, mock)
    
    res = ctrl.run()
    assert res.stop_reason == "final"
    # Should have recovered
    assert any("unknown" in str(s.get("error", "")) for s in ctrl.history)

# --- Integration Test ---
def test_agent_integration(registry, tmp_path):
    mock = MockLLM([
        # Call a disallowed tool
        ToolCall(name="bad", args={}, thought="1"),
        # Learn and call real tool
        ToolCall(name="dummy", args={"query": "data"}, thought="2"),
        # Get result, repeat it to trigger nudge
        ToolCall(name="dummy", args={"query": "data"}, thought="3"),
        # Get nudge, give final verified answer
        FinalAnswer(payload={
            "summary": "Integration",
            "findings": [{"claim": "found", "numbers": [100], "evidence_ids": ["E1"]}],
            "root_cause": "N/A", "quantified_impact": "N/A", "recommendation": "N/A", "caveats": []
        })
    ])
    ctx = ContextManager("sys", {}, {})
    tracer = Tracer(run_id="run5", trace_dir=str(tmp_path))
    ctrl = RunController(ctx, registry, ["dummy"], RunBudget(), tracer, mock)
    
    res = ctrl.run()
    assert res.stop_reason == "final"
    assert res.verified
