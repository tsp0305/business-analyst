import json
import os

def pause_for_user(controller, run_id: str, state_dir: str = "data/state") -> str:
    os.makedirs(state_dir, exist_ok=True)
    state = {
        "history": controller.history,
        "ledger": controller.ledger.evidence,
        "step_counter": controller.step_counter
    }
    filepath = os.path.join(state_dir, f"{run_id}.json")
    with open(filepath, "w") as f:
        json.dump(state, f)
    return filepath

def resume_from_user(filepath: str, user_reply: str, llm_client, registry, tracer):
    with open(filepath, "r") as f:
        state = json.load(f)
    
    from core.agent_loop import RunController, RunBudget
    from core.context import ContextManager
    from core.evidence import EvidenceLedger
    
    ctx = ContextManager("", {}, {}) # Should be reconstructed in real app
    ledger = EvidenceLedger()
    ledger.evidence = state["ledger"]
    
    ctrl = RunController(ctx, registry, [], RunBudget(), tracer, llm_client)
    ctrl.history = state["history"]
    ctrl.step_counter = state["step_counter"]
    
    # inject user reply
    ctrl.history.append({"tool": "ask_user", "args": {}, "result": user_reply})
    return ctrl
