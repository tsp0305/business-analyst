import os
import duckdb
from core.sql_guard import check_sql

class DBContext:
    def __init__(self, db_path="workspace/db.duckdb"):
        self.db_path = db_path
        if db_path != ":memory:":
            dir_name = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(dir_name, exist_ok=True)
        try:
            self.conn = duckdb.connect(db_path)
        except Exception:
            try:
                self.conn = duckdb.connect(db_path, read_only=True)
            except Exception:
                self.conn = duckdb.connect(":memory:")
        self.schema = {}
        self._introspect()

    def load_csv(self, path: str, table_name: str):
        safe_path = path.replace("\\", "/")
        self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{safe_path}')")
        self._introspect()

    def _introspect(self):
        tables = self.conn.execute("SHOW TABLES").fetchall()
        self.schema = {}
        for t in tables:
            t_name = t[0]
            cols = self.conn.execute(f"PRAGMA table_info('{t_name}')").fetchall()
            self.schema[t_name] = [c[1] for c in cols]

    def get_schema(self) -> dict:
        self._introspect()
        return self.schema

    def list_tables(self) -> list:
        self._introspect()
        return list(self.schema.keys())

    def table_exists(self, table_name: str) -> bool:
        return table_name.lower() in [t.lower() for t in self.list_tables()]

    def execute(self, query: str) -> list | dict:
        self._introspect()
        res = check_sql(query, self.schema)
        if not res["ok"]:
            return {"error": res["error"], "suggestions": res["suggestions"]}
        
        try:
            return self.conn.execute(res["sql_rewritten"]).fetchall()
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
