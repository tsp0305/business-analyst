import json
from pydantic import BaseModel
from typing import Callable, Any, Dict, List

class Tool(BaseModel):
    name: str
    description: str
    args_schema: Any
    func: Callable
    timeout_s: float = 10.0
    max_result_chars: int = 4000

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def execute(self, name: str, args: dict, allowed_tools: List[str]) -> dict:
        if name not in allowed_tools or name not in self.tools:
            return {"error": f"Tool '{name}' is not allowed or unknown.", "hint": "Use a tool from allowed_tools."}
        
        tool = self.tools[name]
        try:
            # Validate args
            parsed_args = tool.args_schema(**args)
        except Exception as e:
            return {"error": f"Invalid args: {str(e)}", "hint": "Check tool schema."}

        try:
            import multiprocessing
            import time
            start = time.time()
            result = tool.func(parsed_args.model_dump())
            if time.time() - start > tool.timeout_s:
                return {"error": "timeout", "hint": "Query took too long."}
            
            res_str = str(result)
            if len(res_str) > tool.max_result_chars:
                return {"compacted": True, "data": res_str[:tool.max_result_chars] + "..."}
            return result
        except Exception as e:
            return {"error": str(e), "hint": "Check your arguments or tool constraints."}

    def has_tool(self, name: str) -> bool:
        return name in self.tools

    def get_tool(self, name: str) -> Tool:
        return self.tools[name]

    def get_tool_schema(self, name: str) -> dict:
        return self.tools[name].args_schema.model_json_schema()
