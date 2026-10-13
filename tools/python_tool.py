from pydantic import BaseModel, Field
from core.tools import Tool
import sys
from io import StringIO
import traceback

class RunPythonArgs(BaseModel):
    code: str = Field(description="Python code to execute.")

def get_tool(db, csv_path: str, out_table: str) -> Tool:
    def func(args: dict) -> dict:
        code = args["code"]
        
        # Setup environment for the code
        env = {
            "db": db,
            "csv_path": csv_path,
            "out_table": out_table
        }
        
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()
        
        try:
            exec(code, env)
            output = redirected_output.getvalue()
            return {"stdout": output}
        except Exception as e:
            err = traceback.format_exc()
            return {"error": err}
        finally:
            sys.stdout = old_stdout

    return Tool(
        name="run_python",
        description="Execute a Python script. Variables `db` (DBContext), `csv_path` (str), and `out_table` (str) are available in the global scope.",
        args_schema=RunPythonArgs,
        func=func,
        timeout_s=30.0,
        max_result_chars=4000
    )
