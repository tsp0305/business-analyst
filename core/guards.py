import json

def check_guards(history: list) -> str | None:
    if len(history) >= 2:
        last = history[-1]
        prev = history[-2]
        
        # repeat check
        if last.get("tool") == prev.get("tool") and last.get("args") == prev.get("args"):
            if len(history) >= 3 and history[-3].get("tool") == last.get("tool") and history[-3].get("args") == last.get("args"):
                return "FORCE_FINAL"
            return "REPEAT: You just called this tool with these exact arguments. Try something else."
    
    # oscillation check A-B-A-B
    if len(history) >= 4:
        if (history[-1].get("tool") == history[-3].get("tool") and history[-1].get("args") == history[-3].get("args") and
            history[-2].get("tool") == history[-4].get("tool") and history[-2].get("args") == history[-4].get("args")):
            return "OSCILLATION: You are switching back and forth between the same actions."

    # no new evidence for 3 steps
    if len(history) >= 3:
        if all("error" in step for step in history[-3:]):
            if len(history) >= 4 and "error" in history[-4]:
                return "FORCE_FINAL"
            return "NO NEW EVIDENCE: You have failed to gather new evidence for 3 steps. Revise your plan."
            
    return None
