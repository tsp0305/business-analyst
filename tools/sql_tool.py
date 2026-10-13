from pydantic import BaseModel, Field
from core.tools import Tool

class RunSqlArgs(BaseModel):
    query: str = Field(description="The SQL query to run. Must be a SELECT.")

def get_tool(db) -> Tool:
    def func(args: dict) -> dict | list:
        query = args["query"]
        res = db.execute(query)
        # db.execute returns dict with 'error' if it fails, or list of tuples
        return res

    return Tool(
        name="run_sql",
        description="Run a raw SQL query against the database. Use for exploratory analysis or when specific metrics are not covered by other tools.",
        args_schema=RunSqlArgs,
        func=func
    )
