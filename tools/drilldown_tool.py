from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any, Dict
from core.tools import Tool
import pandas as pd
from tools.base_tool import validate_table_and_columns, build_where_clause, execute_with_timeout, FilterCondition, GRAIN_RESAMPLE_MAP

class DrilldownArgs(BaseModel):
    table: str
    metric: str
    date_column: str
    dimensions: List[str]
    aggregation: Optional[str] = Field(default="sum", description="SUM, AVG, COUNT, MIN, MAX")
    grain: Optional[str] = Field(default="month", description="day, week, month, quarter, year")
    filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]] = None

def get_tool(db) -> Tool:
    def func(args: dict) -> dict:
        table = args["table"]
        metric = args["metric"]
        date_col = args["date_column"]
        dims = args["dimensions"]
        agg = (args.get("aggregation") or "sum").upper()
        grain = (args.get("grain") or "month").lower()
        filters = args.get("filters")

        validation_err = validate_table_and_columns(db, table, [metric, date_col] + dims)
        if validation_err:
            return validation_err

        schema = db.get_schema()
        real_table = {k.lower(): k for k in schema}[table.lower()]
        valid_cols = schema[real_table]

        safe_dims = [f'"{d}"' for d in dims]
        dim_str = ", ".join(safe_dims)
        where = build_where_clause(filters, valid_cols)
        query = f'SELECT {dim_str}, "{date_col}", {agg}("{metric}") as value FROM "{real_table}" {where} GROUP BY {dim_str}, "{date_col}"'

        res = execute_with_timeout(db.conn, query, timeout_s=15.0)
        if isinstance(res, dict) and "error" in res:
            return res

        df = pd.DataFrame(res, columns=dims + [date_col, "value"])
        if df.empty:
            return {"error": "No data available for drilldown"}

        df[date_col] = pd.to_datetime(df[date_col])

        max_dt = df[date_col].max()
        if pd.isna(max_dt):
            return {"error": "No valid dates found"}

        # Compute period boundaries based on grain
        if grain == "day":
            last_start = max_dt.floor('D')
            prior_end = last_start - pd.Timedelta(seconds=1)
            prior_start = last_start - pd.Timedelta(days=1)
        elif grain == "week":
            last_start = max_dt - pd.Timedelta(days=max_dt.weekday())
            prior_end = last_start - pd.Timedelta(seconds=1)
            prior_start = last_start - pd.Timedelta(weeks=1)
        elif grain == "year":
            last_start = max_dt.replace(month=1, day=1)
            prior_end = last_start - pd.Timedelta(days=1)
            prior_start = prior_end.replace(month=1, day=1)
        else: # month default
            last_start = max_dt.replace(day=1)
            prior_end = last_start - pd.Timedelta(days=1)
            prior_start = prior_end.replace(day=1)

        last = df[df[date_col] >= last_start].groupby(dims)['value'].sum()
        prior = df[(df[date_col] >= prior_start) & (df[date_col] <= prior_end)].groupby(dims)['value'].sum()

        diff = (last - prior).fillna(0)
        diff_sorted = diff[diff.abs() > 0].sort_values(key=abs, ascending=False)

        changes = []
        for idx, val in diff_sorted.head(10).items():
            if not isinstance(idx, tuple):
                idx = (idx,)
            changes.append({
                "dimension_values": dict(zip(dims, idx)),
                "change": float(val)
            })

        return {"changes": changes, "grain": grain}

    return Tool(
        name="drilldown_by_dimension",
        description="Rank dimension combinations by their contribution to the change in a metric (period over period).",
        args_schema=DrilldownArgs,
        func=func
    )
