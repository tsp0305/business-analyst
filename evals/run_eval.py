import argparse
import os
import json
from evals.generate_data import generate_sales_data
from phases.phase1_etl import run_phase_1
from phases.phase2_analysis import run_phase_2
from core.llm import LLMClient, MockLLM
from core.schemas import ToolCall, FinalAnswer
from core.db import DBContext

def evaluate_result(result: dict, truth: dict) -> dict:
    answer = result.get("answer", {})
    findings = answer.get("findings", [])
    
    score = 0
    checks = []
    
    # Check 1: Found South Electronics drop?
    found_drop = False
    for f in findings:
        claim = f.get("claim", "")
        if "South" in claim and "Electronics" in claim:
            found_drop = True
            break
        elif "South" in str(f) and "Electronics" in str(f):
            found_drop = True
            break
            
    if found_drop:
        score += 50
        checks.append("Found South Electronics drop")
    else:
        checks.append("Missed South Electronics drop")
        
    # Check 2: Found North Clothing anomaly?
    # (The test Mock doesn't include it, but the eval could)
    found_anomaly = False
    for f in findings:
        if "North" in str(f) and "Clothing" in str(f):
            found_anomaly = True
            break
            
    if found_anomaly:
        score += 50
        checks.append("Found North Clothing anomaly")
    else:
        checks.append("Missed North Clothing anomaly")
        
    return {
        "score": score,
        "checks": checks
    }

def main(dry_run=False, base_dir="data"):
    os.makedirs(base_dir, exist_ok=True)
    csv_path = os.path.join(base_dir, "eval_sales.csv")
    truth_path = os.path.join(base_dir, "eval_truth.json")
    
    # 1. Generate data
    generate_sales_data(seed=123, output_csv=csv_path, output_truth=truth_path)
    with open(truth_path) as f:
        truth = json.load(f)
        
    # 2. Setup LLM
    if dry_run:
        # Mock script for dry run
        mock_phase1 = MockLLM([
            ToolCall(name="run_python", args={"code": f"import pandas as pd\\ndf=pd.read_csv('{csv_path.replace(chr(92), '/')}')\\ndb.conn.execute('CREATE TABLE cleaned_sales AS SELECT * FROM df')"}, thought="run python"),
            FinalAnswer(payload={"table_name": "cleaned_sales", "row_count": 100})
        ])
        # We need a separate mock for phase 2
        mock_phase2 = MockLLM([
            ToolCall(name="trend_analysis", args={"table": "cleaned_sales", "metric": "rev_amt", "date_column": "ord_dt", "filters": None}, thought="check trend"),
            FinalAnswer(payload={
                "summary": "Revenue dropped",
                "findings": [
                    {"claim": "South Electronics dropped", "numbers": [], "evidence_ids": ["E1"]},
                    {"claim": "North Clothing spike", "numbers": [], "evidence_ids": ["E1"]}
                ],
                "root_cause": "Unknown",
                "quantified_impact": "",
                "recommendation": "Investigate",
                "caveats": []
            })
        ])
        llm1 = mock_phase1
        llm2 = mock_phase2
    else:
        # In real mode, use the actual provider client
        # But wait, LLMClient currently needs a provider_client. We will assume user configures it later.
        llm1 = LLMClient(mode="live")
        llm2 = LLMClient(mode="live")
        
    # 3. Phase 1
    db = DBContext()
    res1 = run_phase_1(llm1, csv_path, "cleaned_sales", trace_dir=os.path.join(base_dir, "traces"), db=db)
    if not res1["success"]:
        return {"success": False, "error": "Phase 1 failed"}
        
    # 4. Phase 2
    res2 = run_phase_2(llm2, "Why did revenue drop last month?", "cleaned_sales", db, trace_dir=os.path.join(base_dir, "traces"))
    if not res2["success"]:
        return {"success": False, "error": "Phase 2 failed"}
        
    # 5. Evaluate
    eval_result = evaluate_result(res2, truth)
    eval_result["success"] = True
    return eval_result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    result = main(dry_run=args.dry_run)
    print("Eval Result:", result)
