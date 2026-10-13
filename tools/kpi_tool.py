from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any, Dict
from core.tools import Tool
from tools.base_tool import validate_table_and_columns, build_where_clause, execute_with_timeout, FilterCondition

class ComputeKPIArgs(BaseModel):
    table: str
    kpi: str = Field(description="The numeric column to aggregate.")
    aggregation: Optional[str] = Field(default="sum", description="SUM, AVG, COUNT, MIN, MAX")
    filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]] = Field(default=None, description="Structured filters or WHERE condition")

def get_tool(db) -> Tool:
    def func(args: dict) -> dict:
        table = args["table"]
        kpi = args["kpi"]
        agg = (args.get("aggregation") or "sum").upper()
        filters = args.get("filters")

        if agg not in ("SUM", "AVG", "COUNT", "MIN", "MAX"):
            return {"error": f"Unsupported aggregation '{agg}'. Use SUM, AVG, COUNT, MIN, or MAX.", "hint": "Valid: SUM, AVG, COUNT, MIN, MAX"}

        validation_err = validate_table_and_columns(db, table, [kpi])
        if validation_err:
            return validation_err

        schema = db.get_schema()
        real_table = {k.lower(): k for k in schema}[table.lower()]
        valid_cols = schema[real_table]

        where = build_where_clause(filters, valid_cols)
        query = f'SELECT {agg}("{kpi}") as value FROM "{real_table}" {where}'

        res = execute_with_timeout(db.conn, query, timeout_s=10.0)
        if isinstance(res, dict) and "error" in res:
            return res

        val = res[0][0] if res and res[0] else None
        return {"kpi": kpi, "aggregation": agg, "value": val}

    return Tool(
        name="compute_kpi",
        description="Compute an aggregate KPI (SUM, AVG, COUNT, MIN, MAX) over a specific column with optional filters.",
        args_schema=ComputeKPIArgs,
        func=func
    )
