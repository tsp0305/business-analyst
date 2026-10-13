from pydantic import BaseModel, Field
from typing import List, Dict, Any
from core.tools import Tool
import plotly.express as px
import json
import uuid
import os

class ChartArgs(BaseModel):
    chart_type: str = Field(description="bar, line, or scatter")
    data: List[Dict[str, Any]]
    x_col: str
    y_col: str
    title: str

def get_tool() -> Tool:
    def func(args: dict) -> dict:
        chart_type = args["chart_type"].lower()
        data = args["data"]
        x_col = args["x_col"]
        y_col = args["y_col"]
        title = args["title"]
        
        if not data:
            return {"error": "No data provided for chart."}
            
        import pandas as pd
        df = pd.DataFrame(data)
        
        try:
            if chart_type == "bar":
                fig = px.bar(df, x=x_col, y=y_col, title=title)
            elif chart_type == "line":
                fig = px.line(df, x=x_col, y=y_col, title=title)
            else:
                fig = px.scatter(df, x=x_col, y=y_col, title=title)
                
            chart_id = str(uuid.uuid4())
            os.makedirs("data/charts", exist_ok=True)
            with open(f"data/charts/{chart_id}.json", "w") as f:
                f.write(fig.to_json())
                
            return {"chart_id": chart_id, "status": "saved"}
        except Exception as e:
            return {"error": f"Failed to generate chart: {e}"}

    return Tool(
        name="make_chart",
        description="Generate a chart and save it. Returns a chart_id that you should include in your answer.",
        args_schema=ChartArgs,
        func=func
    )
