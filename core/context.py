import json

def format_catalog(catalog: dict) -> str:
    if not catalog:
        return "Dataset Catalog: None"
    lines = ["Dataset Catalog:"]
    for table_name, meta in catalog.items():
        row_count = meta.get("row_count", "unknown")
        lines.append(f"Table: `{table_name}` ({row_count} rows)")
        columns = meta.get("columns", [])
        for col in columns:
            c_name = col.get("name")
            c_type = col.get("type")
            c_role = col.get("role", "dimension")
            null_pct = col.get("null_pct", 0.0)
            samples = col.get("sample_values", [])
            samples_str = f", sample values: {samples[:3]}" if samples else ""
            lines.append(f"  - `{c_name}` ({c_type}, role: {c_role}, nulls: {null_pct}%{samples_str})")
    return "\n".join(lines)

class ContextManager:
    def __init__(self, system_prompt: str, catalog: dict = None, tool_schemas: dict = None, dictionary: dict = None, relationships: dict = None):
        self.system_prompt = system_prompt
        self.catalog = catalog or {}
        self.tool_schemas = tool_schemas or {}
        self.dictionary = dictionary or {}
        self.relationships = relationships or {}
        self.thread_memory = []

    def build_prompt(self, history: list, ledger_index: str, max_tokens: int = 4000) -> list:
        catalog_text = format_catalog(self.catalog)
        tools_text = json.dumps(self.tool_schemas, indent=2) if self.tool_schemas else "None"
        
        sys_msg = (
            f"{self.system_prompt}\n\n"
            f"{catalog_text}\n\n"
            f"Available Tool Schemas:\n{tools_text}\n\n"
            f"Evidence Ledger:\n{ledger_index}"
        )
        
        messages = [{"role": "system", "content": sys_msg}]
        for m in self.thread_memory:
            messages.append(m)
            
        # Add history (last 4 steps)
        for step in history[-4:]:
            messages.append({"role": "assistant", "content": json.dumps({"tool": step.get("tool"), "args": step.get("args")})})
            messages.append({"role": "user", "content": str(step.get("result", step.get("error")))})
            
        return messages
