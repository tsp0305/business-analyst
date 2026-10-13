import threading
import difflib
from pydantic import BaseModel, Field
from typing import Optional, Any, List, Union, Dict

class FilterCondition(BaseModel):
    column: str
    op: str = Field(default="=", description="=, !=, >, >=, <, <=, LIKE, IN, IS NULL, IS NOT NULL")
    value: Any = None

def validate_table_and_columns(db, table: str, columns: List[str] = None) -> Optional[Dict[str, Any]]:
    schema = db.get_schema()
    tables_lower = {k.lower(): k for k in schema}

    if table.lower() not in tables_lower:
        matches = difflib.get_close_matches(table, list(schema.keys()))
        hint = f"Did you mean {matches}?" if matches else "Table does not exist."
        return {"error": f"Table '{table}' not found in database.", "hint": hint}

    real_table = tables_lower[table.lower()]
    valid_cols = schema[real_table]
    valid_cols_lower = {c.lower(): c for c in valid_cols}

    if columns:
        for col in columns:
            if not col or col == "*":
                continue
            if col.lower() not in valid_cols_lower:
                matches = difflib.get_close_matches(col, valid_cols)
                hint = f"Did you mean {matches}?" if matches else f"Valid columns for '{real_table}' are: {valid_cols}"
                return {"error": f"Column '{col}' not found in table '{real_table}'.", "hint": hint}

    return None

def build_where_clause(filters: Optional[Union[List[Union[FilterCondition, Dict[str, Any]]], str]], valid_cols: List[str] = None) -> str:
    if not filters:
        return ""

    if isinstance(filters, list):
        clauses = []
        valid_lower = {c.lower(): c for c in valid_cols} if valid_cols else {}

        for f in filters:
            if isinstance(f, dict):
                col = f.get("column")
                op = (f.get("op") or "=").strip()
                val = f.get("value")
            else:
                col = f.column
                op = (f.op or "=").strip()
                val = f.value

            if not col:
                continue

            # Quote identifier
            safe_col = f'"{valid_lower.get(col.lower(), col)}"'
            op_upper = op.upper()

            if op_upper in ("IS NULL", "IS NOT NULL"):
                clauses.append(f"{safe_col} {op_upper}")
            elif isinstance(val, (int, float)):
                clauses.append(f"{safe_col} {op} {val}")
            elif isinstance(val, (list, tuple)):
                in_str = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in val)
                clauses.append(f"{safe_col} IN ({in_str})")
            else:
                safe_val = str(val).replace("'", "''")
                clauses.append(f"{safe_col} {op} '{safe_val}'")

        return f"WHERE {' AND '.join(clauses)}" if clauses else ""

    if isinstance(filters, str):
        cleaned = filters.strip()
        if not cleaned:
            return ""
        if cleaned.upper().startswith("WHERE"):
            return cleaned
        return f"WHERE {cleaned}"

    return ""

def execute_with_timeout(conn, query: str, timeout_s: float = 10.0):
    result_box = [None]
    error_box = [None]
    done_evt = threading.Event()

    def worker():
        try:
            result_box[0] = conn.execute(query).fetchall()
        except Exception as e:
            error_box[0] = e
        finally:
            done_evt.set()

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=timeout_s)

    if not done_evt.is_set():
        try:
            conn.interrupt()
        except Exception:
            pass
        t.join(timeout=1.0)
        return {"error": "Query timeout exceeded", "hint": f"Execution exceeded {timeout_s}s limit."}

    if error_box[0]:
        return {"error": str(error_box[0]), "hint": "Check query syntax and constraints."}

    return result_box[0]

GRAIN_RESAMPLE_MAP = {
    "day": "D",
    "week": "W",
    "month": "ME",
    "quarter": "QE",
    "year": "YE"
}
