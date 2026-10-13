import json
import os

class Tracer:
    def __init__(self, run_id: str, trace_dir: str = "data/traces"):
        self.run_id = run_id
        self.trace_dir = trace_dir
        os.makedirs(self.trace_dir, exist_ok=True)
        self.filepath = os.path.join(self.trace_dir, f"{self.run_id}.jsonl")
        
    def log_step(self, step_data: dict):
        with open(self.filepath, "a") as f:
            f.write(json.dumps(step_data) + "\n")
