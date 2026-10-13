from core.agent_loop import RunController, RunBudget
from core.context import ContextManager
from core.tools import ToolRegistry
from core.trace import Tracer
from tools import get_analytics_tools
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json as _json

class Finding(BaseModel):
    claim: str
    numbers: List[float]
    evidence_ids: List[str]

class AnswerSchema(BaseModel):
    summary: str
    findings: List[Finding]
    root_cause: str
    quantified_impact: str
    recommendation: str
    caveats: List[str]

def run_phase_2(llm_client, question: str, table_name: str, db, trace_dir: str = "data/traces", state_dir: str = "data/state") -> dict:
    registry = ToolRegistry()
    for tool in get_analytics_tools(db):
        registry.register(tool)
        
    allowed_tools = [
        "run_sql", "compute_kpi", "trend_analysis", 
        "detect_anomalies", "forecast", "drilldown_by_dimension", 
        "make_chart", "ask_user"
    ]
    
    # Retrieve catalog directly from DBContext (or introspect schema)
    if hasattr(db, "catalog") and db.catalog:
        catalog = db.catalog
    else:
        catalog = {}
        for t, cols in db.get_schema().items():
            try:
                row_count = db.conn.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
            except Exception:
                row_count = 0
            catalog[t] = {
                "table_name": t,
                "row_count": row_count,
                "columns": [{"name": c, "type": "UNKNOWN", "role": "dimension"} for c in cols]
            }

    # Extract tool JSON argument schemas for grounding
    tool_schemas = {}
    for tool_name in allowed_tools:
        if registry.has_tool(tool_name):
            tool = registry.get_tool(tool_name)
            tool_schemas[tool_name] = tool.args_schema.model_json_schema() if tool.args_schema else {}

    sys_prompt = f"""You are a senior Business Intelligence Analyst.
The user has asked: "{question}"
Target table context: `{table_name}`.

Instructions:
1. Ground your investigation strictly in the registered Dataset Catalog.
2. When multiple datasets exist and the user's question is ambiguous, call `ask_user` to ask which dataset or metric is meant.
3. Use your allowed tools to investigate. Gather numerical evidence carefully.
4. When finished, you must return a FinalAnswer matching this exact schema:
{_json.dumps(AnswerSchema.model_json_schema(), indent=2)}
"""

    ctx = ContextManager(system_prompt=sys_prompt, catalog=catalog, tool_schemas=tool_schemas)
    tracer = Tracer(run_id=f"phase2_{uuid.uuid4()}", trace_dir=trace_dir)
    budget = RunBudget(max_steps=10, max_consecutive_errors=3)

    ctrl = RunController(
        context_manager=ctx,
        tool_registry=registry,
        allowed_tools=allowed_tools,
        budget=budget,
        tracer=tracer,
        llm_client=llm_client,
        output_schema=AnswerSchema
    )

    res = ctrl.run()

    # Handle Human-in-the-Loop clarification
    state_file = None
    if res.stop_reason == "user_input_needed":
        from core.hitl import pause_for_user
        state_file = pause_for_user(ctrl, f"phase2_paused_{uuid.uuid4()}", state_dir)
        return {
            "success": False,
            "error": "Clarification required from user",
            "answer": res.answer or {},
            "verified": False,
            "stop_reason": "user_input_needed",
            "trace": res.trace,
            "state_file": state_file
        }

    # Return error clearly if LLM failed or budget exhausted without findings
    if not res.answer or not res.answer.get("findings"):
        return {
            "success": False,
            "error": f"Analysis failed: {res.stop_reason}",
            "answer": res.answer or {},
            "verified": False,
            "stop_reason": res.stop_reason,
            "trace": res.trace
        }

    return {
        "success": True,
        "answer": res.answer,
        "verified": res.verified,
        "stop_reason": res.stop_reason,
        "trace": res.trace
    }
