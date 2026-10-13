from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any, Dict
from core.tools import Tool
import pandas as pd
import numpy as np
from tools.base_tool import validate_table_and_columns, build_where_clause, execute_with_timeout, FilterCondition, GRAIN_RESAMPLE_MAP

class AnomalyArgs(BaseModel):
    table: str
    metric: str
    date_column: str
    method: Optional[str] = Field(default="zscore", description="'zscore' or 'iqr'")
    aggregation: Optional[str] = Field(default="sum", description="SUM, AVG, COUNT, MIN, MAX")
    grain: Optional[str] = Field(default="day", description="day, week, month, quarter, year")
    filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]] = None

def get_tool(db) -> Tool:
    def func(args: dict) -> dict:
        table = args["table"]
        metric = args["metric"]
        date_col = args["date_column"]
        method = (args.get("method") or "zscore").lower()
        agg = (args.get("aggregation") or "sum").upper()
        grain = (args.get("grain") or "day").lower()
        filters = args.get("filters")

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
        if len(df) < 5:
            return {"error": "Not enough data for anomaly detection."}

        df[date_col] = pd.to_datetime(df[date_col])
        resample_rule = GRAIN_RESAMPLE_MAP.get(grain, "D")
        df = df.set_index(date_col).resample(resample_rule).sum().reset_index().dropna()

        anomalies = []
        if method == "zscore":
            mean = df['value'].mean()
            std = df['value'].std()
            if std > 0:
                df['z'] = (df['value'] - mean) / std
                out = df[np.abs(df['z']) > 3]
                anomalies = out[date_col].dt.strftime('%Y-%m-%d').tolist()
        elif method == "iqr":
            q1 = df['value'].quantile(0.25)
            q3 = df['value'].quantile(0.75)
            iqr = q3 - q1
            out = df[(df['value'] < q1 - 1.5 * iqr) | (df['value'] > q3 + 1.5 * iqr)]
            anomalies = out[date_col].dt.strftime('%Y-%m-%d').tolist()

        return {"anomalies": anomalies, "count": len(anomalies), "method": method, "grain": grain}

    return Tool(
        name="detect_anomalies",
        description="Detect time-series spikes or dips in a metric using zscore or iqr at specified grain.",
        args_schema=AnomalyArgs,
        func=func
    )
