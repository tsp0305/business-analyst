from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any, Dict
from core.tools import Tool
import pandas as pd
from tools.base_tool import validate_table_and_columns, build_where_clause, execute_with_timeout, FilterCondition, GRAIN_RESAMPLE_MAP

class TrendAnalysisArgs(BaseModel):
    table: str
    metric: str
    date_column: str
    aggregation: Optional[str] = Field(default="sum", description="SUM, AVG, COUNT, MIN, MAX")
    grain: Optional[str] = Field(default="month", description="day, week, month, quarter, year")
    filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]] = None

def get_tool(db) -> Tool:
    def func(args: dict) -> dict:
        table = args["table"]
        metric = args["metric"]
        date_col = args["date_column"]
        agg = (args.get("aggregation") or "sum").upper()
        grain = (args.get("grain") or "month").lower()
        filters = args.get("filters")

        if agg not in ("SUM", "AVG", "COUNT", "MIN", "MAX"):
            return {"error": f"Unsupported aggregation '{agg}'.", "hint": "Use SUM, AVG, COUNT, MIN, or MAX."}

        resample_rule = GRAIN_RESAMPLE_MAP.get(grain, "ME")

        validation_err = validate_table_and_columns(db, table, [metric, date_col])
        if validation_err:
            return validation_err

        schema = db.get_schema()
        real_table = {k.lower(): k for k in schema}[table.lower()]
        valid_cols = schema[real_table]

        where = build_where_clause(filters, valid_cols)
        query = f'SELECT "{date_col}", {agg}("{metric}") as value FROM "{real_table}" {where} GROUP BY "{date_col}"'

        res = execute_with_timeout(db.conn, query, timeout_s=15.0)
        if isinstance(res, dict) and "error" in res:
            return res

        df = pd.DataFrame(res, columns=[date_col, "value"])
        if df.empty:
            return {"error": "No data found for trend."}

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()

        # Resample by chosen grain
        if agg == "AVG":
            resampled = df.resample(resample_rule).mean()
        elif agg == "MAX":
            resampled = df.resample(resample_rule).max()
        elif agg == "MIN":
            resampled = df.resample(resample_rule).min()
        elif agg == "COUNT":
            resampled = df.resample(resample_rule).count()
        else:
            resampled = df.resample(resample_rule).sum()

        resampled = resampled.dropna()
        if len(resampled) < 2:
            return {"error": f"Not enough data to compare periods at grain '{grain}'."}

        last_val = float(resampled.iloc[-1]['value'])
        prior_val = float(resampled.iloc[-2]['value'])
        diff = last_val - prior_val
        pct = round(((diff) / prior_val * 100), 2) if prior_val != 0 else 0.0

        return {
            "last_period": last_val,
            "prior_period": prior_val,
            # Backwards compatibility keys
            "last_month": last_val,
            "prior_month": prior_val,
            "diff": round(diff, 2),
            "percent_change": pct,
            "grain": grain,
            "aggregation": agg
        }

    return Tool(
        name="trend_analysis",
        description="Compare a metric in the most recent period vs prior period (day, week, month, quarter, year).",
        args_schema=TrendAnalysisArgs,
        func=func
    )
