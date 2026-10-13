import sqlglot
import difflib

BLOCKED_FUNC_NAMES = {
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_ndjson_auto",
    "glob",
    "scan",
    "copy",
    "attach",
    "install",
    "load",
    "pragma",
    "httpfs",
    "s3",
    "readcsv",
    "readparquet",
    "readjson",
    "readndjson"
}

BLOCKED_NODE_TYPES = (
    sqlglot.exp.Insert,
    sqlglot.exp.Update,
    sqlglot.exp.Delete,
    sqlglot.exp.Drop,
    sqlglot.exp.Alter,
    sqlglot.exp.Create,
    sqlglot.exp.Command,
    sqlglot.exp.Pragma
)

def check_sql(query: str, schema: dict) -> dict:
    if not query or not query.strip():
        return {"ok": False, "error": "Empty query", "suggestions": []}

    try:
        parsed = sqlglot.parse(query, read="duckdb")
    except Exception as e:
        return {"ok": False, "error": f"Parse error: {e}", "suggestions": []}

    if not parsed or len(parsed) != 1:
        return {"ok": False, "error": "Multiple statements not allowed", "suggestions": []}

    stmt = parsed[0]
    if stmt is None or not isinstance(stmt, (sqlglot.exp.Select, sqlglot.exp.Union)):
        return {"ok": False, "error": "Blocked statement (only SELECT allowed)", "suggestions": []}

    # Ensure no DDL/DML statements anywhere in the AST
    for blocked_node in stmt.find_all(BLOCKED_NODE_TYPES):
        return {"ok": False, "error": f"Blocked statement ({blocked_node.key.upper()} not allowed)", "suggestions": []}

    # Block table/file/network functions via AST inspection
    for table_expr in stmt.find_all(sqlglot.exp.Table):
        t_this = table_expr.this
        if isinstance(t_this, (sqlglot.exp.Func, sqlglot.exp.Anonymous)):
            key = (getattr(t_this, "key", "") or "").lower()
            name = (getattr(t_this, "name", "") or "").lower()
            sql_head = (t_this.sql().split("(")[0].strip()).lower()
            if key in BLOCKED_FUNC_NAMES or name in BLOCKED_FUNC_NAMES or sql_head in BLOCKED_FUNC_NAMES or any(key.startswith(b) for b in ("read_", "readcsv", "readparquet", "readjson")):
                return {"ok": False, "error": f"Blocked function: {name or key or sql_head}", "suggestions": []}

        t_name = (table_expr.name or "").lower()
        if t_name in BLOCKED_FUNC_NAMES or any(t_name.startswith(b) for b in ("read_", "readcsv", "readparquet", "readjson")):
            return {"ok": False, "error": f"Blocked function: {t_name}", "suggestions": []}

    for func_expr in stmt.find_all((sqlglot.exp.Func, sqlglot.exp.Anonymous)):
        f_key = (getattr(func_expr, "key", "") or "").lower()
        f_name = (getattr(func_expr, "name", "") or "").lower()
        f_sql = (func_expr.sql().split("(")[0].strip()).lower()
        if f_key in BLOCKED_FUNC_NAMES or f_name in BLOCKED_FUNC_NAMES or f_sql in BLOCKED_FUNC_NAMES or any(f_key.startswith(b) for b in ("read_", "readcsv", "readparquet", "readjson")):
            return {"ok": False, "error": f"Blocked function: {f_name or f_key or f_sql}", "suggestions": []}

    # Discover CTE and Subquery names
    cte_names = set()
    for cte in stmt.find_all(sqlglot.exp.CTE):
        if hasattr(cte, "alias_or_name") and cte.alias_or_name:
            cte_names.add(cte.alias_or_name.lower())

    schema_tables_lower = {k.lower(): k for k in schema}

    # Validate table names
    for table_expr in stmt.find_all(sqlglot.exp.Table):
        t_name = (table_expr.name or "").lower()
        if not t_name:
            # Check if it was a table function that bypassed earlier check
            if isinstance(table_expr.this, (sqlglot.exp.Func, sqlglot.exp.Anonymous)):
                return {"ok": False, "error": f"Blocked table function: {table_expr.this.key}", "suggestions": []}
            continue
        if t_name in cte_names:
            continue
        if t_name not in schema_tables_lower:
            matches = difflib.get_close_matches(table_expr.name, list(schema.keys()))
            suggestion = f"Unknown table {table_expr.name}, did you mean {matches}?" if matches else f"Unknown table {table_expr.name}"
            return {"ok": False, "error": f"Unknown table {table_expr.name}", "suggestions": [suggestion]}

    # Collect SELECT aliases across all Select expressions
    select_aliases = set()
    for select_node in stmt.find_all(sqlglot.exp.Select):
        for expr in select_node.expressions:
            if isinstance(expr, sqlglot.exp.Alias) and expr.alias:
                select_aliases.add(expr.alias.lower())

    all_cols = []
    for cols in schema.values():
        all_cols.extend(cols)
    all_cols_lower = {c.lower(): c for c in all_cols}

    # Validate columns
    for column in stmt.find_all(sqlglot.exp.Column):
        col_name = column.name.lower()
        if not col_name or col_name == "*":
            continue

        # Column matches an alias in SELECT or a CTE name
        if col_name in select_aliases or col_name in cte_names:
            continue

        # Check table qualification
        col_table = column.table.lower() if column.table else None
        if col_table and col_table in schema_tables_lower:
            real_table = schema_tables_lower[col_table]
            table_cols_lower = {c.lower(): c for c in schema[real_table]}
            if col_name not in table_cols_lower:
                matches = difflib.get_close_matches(column.name, schema[real_table])
                suggestion = f"Unknown column {column.name}, did you mean {matches}?" if matches else f"Unknown column {column.name}"
                return {"ok": False, "error": f"Unknown column {column.name}", "suggestions": [suggestion]}
        elif col_table and col_table in cte_names:
            # Column belongs to a local CTE
            continue
        else:
            if col_name not in all_cols_lower and not any(col_name in [c.lower() for c in cols] for cols in schema.values()):
                matches = difflib.get_close_matches(column.name, all_cols)
                suggestion = f"Unknown column {column.name}, did you mean {matches}?" if matches else f"Unknown column {column.name}"
                return {"ok": False, "error": f"Unknown column {column.name}", "suggestions": [suggestion]}

    # Inject LIMIT 1000 if not present
    if not stmt.args.get("limit"):
        stmt = stmt.limit(1000)

    return {
        "ok": True,
        "sql_rewritten": stmt.sql(dialect="duckdb"),
        "error": "",
        "suggestions": []
    }
