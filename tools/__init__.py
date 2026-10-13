from typing import List
from core.tools import Tool
from core.db import DBContext

def get_analytics_tools(db: DBContext) -> List[Tool]:
    from .sql_tool import get_tool as sql
    from .kpi_tool import get_tool as kpi
    from .trend_tool import get_tool as trend
    from .anomaly_tool import get_tool as anomaly
    from .forecast_tool import get_tool as forecast
    from .drilldown_tool import get_tool as drill
    from .chart_tool import get_tool as chart
    
    return [
        sql(db),
        kpi(db),
        trend(db),
        anomaly(db),
        forecast(db),
        drill(db),
        chart()
    ]
