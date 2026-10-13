import time
from pydantic import BaseModel
from core.schemas import ToolCall, AskUser, FinalAnswer
from core.evidence import EvidenceLedger
from core.guards import check_guards
from core.verifier import verify_answer

class RunBudget(BaseModel):
    max_steps: int = 8
    max_tokens: int = 60000
    timeout_s: float = 90.0
    max_consecutive_errors: int = 3
    max_repair_rounds: int = 1

class RunResult(BaseModel):
    answer: dict
    trace: list
    stop_reason: str
    usage: dict
    verified: bool

class RunController:
    def __init__(self, context_manager, tool_registry, allowed_tools, budget, tracer, llm_client, output_schema=None):
        self.context = context_manager
        self.registry = tool_registry
        self.allowed_tools = allowed_tools
        self.budget = budget
        self.tracer = tracer
        self.llm = llm_client
        self.output_schema = output_schema
        self.ledger = EvidenceLedger()
        self.history = []
        self.step_counter = 0
        self.start_time = time.time()
        self.consecutive_errors = 0
        self.force_final = False

    def run(self) -> RunResult:
        stop_reason = ""
        verified = False
        final_payload = None

        while True:
            if self.step_counter >= self.budget.max_steps:
                stop_reason = "budget_exhausted"
                self.force_final = True
            
            if time.time() - self.start_time > self.budget.timeout_s:
                stop_reason = "budget_exhausted"
                self.force_final = True
                
            if self.consecutive_errors >= self.budget.max_consecutive_errors:
                stop_reason = stop_reason or "stalled"
                self.force_final = True

            guard_msg = check_guards(self.history)
            if guard_msg == "FORCE_FINAL":
                stop_reason = stop_reason or "stalled"
                self.force_final = True

            messages = self.context.build_prompt(self.history, self.ledger.get_index())
            if guard_msg and guard_msg != "FORCE_FINAL":
                messages.append({"role": "user", "content": f"SYSTEM NUDGE: {guard_msg}"})
            if self.force_final:
                messages.append({"role": "user", "content": "SYSTEM COMMAND: You must return a FinalAnswer now based on evidence gathered so far."})
                
            t0 = time.time()
            action = self.llm.next_action(messages, self.allowed_tools)
            latency = time.time() - t0

            if isinstance(action, ToolCall):
                if self.force_final:
                    # Ignore tool call, pretend error
                    res = {"error": "Forced finalization. Provide FinalAnswer."}
                    eid = None
                else:
                    res = self.registry.execute(action.name, action.args, self.allowed_tools)
                    if "error" in res:
                        self.consecutive_errors += 1
                        eid = None
                    else:
                        self.consecutive_errors = 0
                        eid = self.ledger.add(action.name, action.args, res)
                
                step_data = {
                    "tool": action.name, "args": action.args,
                    "result_summary": str(res)[:100] if "error" not in res else res["error"],
                    "error": res.get("error") if isinstance(res, dict) else None
                }
                self.history.append(step_data)
                
                self.tracer.log_step({
                    "step": self.step_counter, "thought": action.thought,
                    "tool": action.name, "args": action.args, "evidence_id": eid,
                    "latency_ms": latency * 1000, "result_summary": step_data["result_summary"]
                })
                self.step_counter += 1

            elif isinstance(action, AskUser):
                stop_reason = "user_input_needed"
                self.tracer.log_step({"step": self.step_counter, "tool": "ask_user", "args": {"q": action.question}})
                break

            elif isinstance(action, FinalAnswer):
                payload = action.payload
                if isinstance(payload, BaseModel):
                    payload = payload.model_dump()
                elif isinstance(payload, dict):
                    pass
                
                v_res = verify_answer(payload, self.ledger) if payload and isinstance(payload, dict) else {"verified": True}
                if not v_res.get("verified", True) and not self.force_final: # Need repair
                    self.history.append({"tool": "verify", "args": {}, "error": str(v_res["errors"])})
                    self.force_final = True # only 1 repair round
                    continue
                
                final_payload = payload
                verified = v_res.get("verified", True)
                stop_reason = stop_reason or "final"
                self.tracer.log_step({"step": self.step_counter, "tool": "FinalAnswer", "verified": verified})
                break

        return RunResult(
            answer=final_payload or {},
            trace=self.history,
            stop_reason=stop_reason,
            usage={},
            verified=verified
        )
