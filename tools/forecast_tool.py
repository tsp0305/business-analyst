from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any, Dict
from core.tools import Tool
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from tools.base_tool import validate_table_and_columns, build_where_clause, execute_with_timeout, FilterCondition, GRAIN_RESAMPLE_MAP

warnings.simplefilter('ignore', ConvergenceWarning)

class ForecastArgs(BaseModel):
    table: str
    metric: str
    date_column: str
    horizon: int
    grain: Optional[str] = Field(default="day", description="'day', 'week', 'month', or 'year'")
    aggregation: Optional[str] = Field(default="sum", description="SUM, AVG, COUNT, MIN, MAX")
    filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]] = None

def get_tool(db) -> Tool:
    def func(args: dict) -> dict:
        table = args["table"]
        metric = args["metric"]
        date_col = args["date_column"]
        horizon = args["horizon"]
        grain = (args.get("grain") or "day").lower()
        agg = (args.get("aggregation") or "sum").upper()
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
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()

        resample_rule = GRAIN_RESAMPLE_MAP.get(grain, "D")
        df = df.resample(resample_rule).sum().dropna()

        if len(df) < 30 and grain == 'day':
            return {"error": "Series too short for daily forecast."}
        if len(df) < 5:
            return {"error": "Series too short for forecast."}

        try:
            model = ExponentialSmoothing(df['value'], trend='add', seasonal=None, initialization_method="estimated").fit()
            forecast = model.forecast(horizon)
            residuals = model.resid
            std = residuals.std()

            f_list = []
            intervals = []
            for dt, val in forecast.items():
                f_list.append(float(val))
                intervals.append({
                    "date": dt.strftime('%Y-%m-%d'),
                    "value": float(val),
                    "lower": float(val - 1.96 * std),
                    "upper": float(val + 1.96 * std)
                })

            return {"forecast": f_list, "intervals": intervals, "grain": grain}
        except Exception as e:
            return {"error": f"Forecast model fitting failed: {str(e)}"}

    return Tool(
        name="forecast",
        description="Forecast a metric ahead by horizon periods using exponential smoothing.",
        args_schema=ForecastArgs,
        func=func
    )
