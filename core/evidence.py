import time

class EvidenceLedger:
    def __init__(self):
        self.evidence = {}
        self.counter = 1

    def add(self, tool: str, args: dict, result: dict) -> str:
        eid = f"E{self.counter}"
        self.counter += 1
        self.evidence[eid] = {
            "tool": tool,
            "args": args,
            "result": result,
            "timestamp": time.time()
        }
        return eid

    def get(self, eid: str) -> dict:
        return self.evidence.get(eid)

    def get_index(self) -> str:
        lines = []
        for eid, data in self.evidence.items():
            lines.append(f"{eid}: {data['tool']} -> {str(data['result'])[:100]}")
        return "\n".join(lines)
