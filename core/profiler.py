import re
import duckdb
from typing import Dict, Any, List, Optional

SENTINEL_NULLS = {"", "null", "none", "n/a", "na", "nan", "nil", "undefined"}

def infer_column_role(col_name: str, col_type: str, total_rows: int, null_count: int, distinct_count: int, sample_values: list) -> str:
    """
    Infers role strictly from data values and distributions:
    'id', 'date', 'measure', 'dimension', 'text'
    """
    col_type_upper = col_type.upper()
    valid_count = total_rows - null_count

    # 1. Date / Timestamp detection
    if any(t in col_type_upper for t in ("DATE", "TIME", "TIMESTAMP")):
        return "date"

    # Check if string values are parseable dates
    if any(t in col_type_upper for t in ("VARCHAR", "TEXT", "CHAR", "STRING")) and sample_values:
        date_pattern = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}")
        date_matches = sum(1 for v in sample_values if isinstance(v, str) and date_pattern.match(v.strip()))
        if len(sample_values) > 0 and (date_matches / len(sample_values)) >= 0.7:
            return "date"

    # 2. Continuous floating point numbers are always measures
    is_float = any(t in col_type_upper for t in ("DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "REAL"))
    if is_float:
        return "measure"

    # 3. Text/String based unique IDs
    is_string = any(t in col_type_upper for t in ("VARCHAR", "TEXT", "CHAR", "STRING"))
    if is_string:
        if valid_count > 0 and (distinct_count / valid_count) >= 0.95 and null_count == 0:
            return "id"
        if distinct_count <= 100 or (valid_count > 0 and (distinct_count / valid_count) <= 0.4):
            return "dimension"
        return "text"

    # 4. Integer types
    is_int = any(t in col_type_upper for t in ("INT", "BIGINT", "SMALLINT", "TINYINT"))
    if is_int:
        # Check if values look like primary keys: 100% unique, positive, sequential or column name has id/key/code
        name_hint = any(h in col_name.lower() for h in ("id", "key", "code", "uuid", "pk", "num"))
        if null_count == 0 and valid_count > 1 and distinct_count == valid_count and name_hint:
            return "id"
        # Categorical codes
        if distinct_count <= 5 and valid_count > 20:
            return "dimension"
        # Otherwise standard numeric measure (amounts, quantities, salaries, durations)
        return "measure"

    if distinct_count <= 100 or (valid_count > 0 and (distinct_count / valid_count) <= 0.4):
        return "dimension"

    return "measure"

def profile_table(conn, table_name: str) -> Dict[str, Any]:
    """
    Profiles each column in a DuckDB table: type, null %, distinct count, min/max, samples, and role.
    """
    cols_info = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    total_rows = conn.execute(f"SELECT COUNT(*) FROM '{table_name}'").fetchone()[0]

    profiles = []
    for col_meta in cols_info:
        col_name = col_meta[1]
        col_type = col_meta[2]

        if total_rows == 0:
            profiles.append({
                "name": col_name,
                "type": col_type,
                "role": "dimension",
                "null_pct": 0.0,
                "distinct_count": 0,
                "min": None,
                "max": None,
                "sample_values": []
            })
            continue

        safe_col = f'"{col_name}"'
        stats_query = f"""
            SELECT 
                COUNT(*) - COUNT({safe_col}) AS null_count,
                COUNT(DISTINCT {safe_col}) AS distinct_count,
                MIN({safe_col}::VARCHAR) AS min_val,
                MAX({safe_col}::VARCHAR) AS max_val
            FROM '{table_name}'
        """
        try:
            null_count, distinct_count, min_val, max_val = conn.execute(stats_query).fetchone()
        except Exception:
            null_count = conn.execute(f"SELECT COUNT(*) - COUNT({safe_col}) FROM '{table_name}'").fetchone()[0]
            distinct_count = conn.execute(f"SELECT COUNT(DISTINCT {safe_col}) FROM '{table_name}'").fetchone()[0]
            min_val, max_val = None, None

        null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

        sample_rows = conn.execute(f"SELECT DISTINCT {safe_col} FROM '{table_name}' WHERE {safe_col} IS NOT NULL LIMIT 5").fetchall()
        sample_values = [r[0] for r in sample_rows]

        role = infer_column_role(col_name, col_type, total_rows, null_count, distinct_count, sample_values)

        profiles.append({
            "name": col_name,
            "type": col_type,
            "role": role,
            "null_pct": null_pct,
            "null_count": null_count,
            "distinct_count": distinct_count,
            "min": min_val,
            "max": max_val,
            "sample_values": sample_values
        })

    roles = {"id": [], "date": [], "measure": [], "dimension": [], "text": []}
    for p in profiles:
        r = p.get("role", "dimension")
        roles.setdefault(r, []).append(p.get("name"))

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "row_count": total_rows,
        "columns": profiles,
        "roles": roles
    }

def clean_and_profile_dataset(db, source_table: str, clean_table_name: str = None) -> Dict[str, Any]:
    """
    Deterministic data cleaning and catalog creation:
    1. Trim strings and convert sentinel nulls ("", "NULL", "N/A") to SQL NULL.
    2. Try casting dates and numerics safely without silent data loss.
    3. Remove exact duplicate rows.
    4. Remove key duplicates ONLY if a unique-key column is detected with high confidence.
    5. Save into clean_<slug> and build catalog entry.
    """
    conn = db.conn
    slug = source_table.replace("ds_", "").replace("clean_", "")
    out_table = clean_table_name or f"clean_{slug}"

    cleaning_log = []
    initial_rows = conn.execute(f"SELECT COUNT(*) FROM '{source_table}'").fetchone()[0]
    cleaning_log.append({"step": "ingest", "source_table": source_table, "initial_rows": initial_rows})

    raw_profile = profile_table(conn, source_table)
    cols = raw_profile["columns"]

    # Step 1: Build projection expressions with string trimming & sentinel null replacement
    col_projections = []
    for c in cols:
        name = c["name"]
        safe_name = f'"{name}"'
        c_type = c["type"].upper()

        if any(t in c_type for t in ("VARCHAR", "TEXT", "CHAR", "STRING")):
            expr = f"""CASE 
                WHEN TRIM({safe_name}) IN ('', 'NULL', 'null', 'N/A', 'n/a', 'None', 'none', 'NaN', 'nan') THEN NULL 
                ELSE TRIM({safe_name}) 
            END AS {safe_name}"""
        else:
            expr = safe_name
        col_projections.append(expr)

    cleaning_log.append({"step": "null_and_trim", "detail": "Trimmed text and normalized sentinel null values to NULL"})

    temp_stage_1 = f"stage1_{slug}"
    conn.execute(f"CREATE OR REPLACE TEMPORARY TABLE {temp_stage_1} AS SELECT {', '.join(col_projections)} FROM '{source_table}'")

    # Step 2: Safe type casting without dropping data
    stage1_profile = profile_table(conn, temp_stage_1)
    cast_projections = []
    cast_failures_report = []

    for c in stage1_profile["columns"]:
        name = c["name"]
        safe_name = f'"{name}"'
        c_type = c["type"].upper()
        role = c["role"]

        if role == "date" and not any(t in c_type for t in ("DATE", "TIMESTAMP")):
            # Check for cast failures
            fail_count = conn.execute(f"SELECT COUNT(*) FROM {temp_stage_1} WHERE {safe_name} IS NOT NULL AND TRY_CAST({safe_name} AS DATE) IS NULL").fetchone()[0]
            if fail_count == 0:
                cast_projections.append(f"TRY_CAST({safe_name} AS DATE) AS {safe_name}")
                cleaning_log.append({"step": "type_cast", "column": name, "target_type": "DATE", "failures": 0})
            else:
                cast_projections.append(safe_name)
                cast_failures_report.append(f"Column '{name}' had {fail_count} date cast failures; retained original format without dropping data")
        elif role == "measure" and any(t in c_type for t in ("VARCHAR", "TEXT", "STRING")):
            fail_count = conn.execute(f"SELECT COUNT(*) FROM {temp_stage_1} WHERE {safe_name} IS NOT NULL AND TRY_CAST({safe_name} AS DOUBLE) IS NULL").fetchone()[0]
            if fail_count == 0:
                cast_projections.append(f"TRY_CAST({safe_name} AS DOUBLE) AS {safe_name}")
                cleaning_log.append({"step": "type_cast", "column": name, "target_type": "DOUBLE", "failures": 0})
            else:
                cast_projections.append(safe_name)
                cast_failures_report.append(f"Column '{name}' had {fail_count} numeric cast failures; retained original format")
        else:
            cast_projections.append(safe_name)

    if cast_failures_report:
        cleaning_log.append({"step": "cast_warnings", "details": cast_failures_report})

    temp_stage_2 = f"stage2_{slug}"
    conn.execute(f"CREATE OR REPLACE TEMPORARY TABLE {temp_stage_2} AS SELECT {', '.join(cast_projections)} FROM {temp_stage_1}")

    # Step 3: Exact row deduplication
    stage2_rows = conn.execute(f"SELECT COUNT(*) FROM {temp_stage_2}").fetchone()[0]
    temp_stage_3 = f"stage3_{slug}"
    conn.execute(f"CREATE OR REPLACE TEMPORARY TABLE {temp_stage_3} AS SELECT DISTINCT * FROM {temp_stage_2}")
    distinct_rows = conn.execute(f"SELECT COUNT(*) FROM {temp_stage_3}").fetchone()[0]
    exact_dupes_dropped = stage2_rows - distinct_rows

    cleaning_log.append({
        "step": "exact_deduplication",
        "rows_before": stage2_rows,
        "rows_after": distinct_rows,
        "dropped": exact_dupes_dropped
    })

    # Step 4: Key deduplication ONLY if a unique-key column is detected with high confidence
    stage3_profile = profile_table(conn, temp_stage_3)
    id_candidates = [c for c in stage3_profile["columns"] if c["role"] == "id" and c["null_count"] == 0]

    date_cols = [c["name"] for c in stage3_profile["columns"] if c["role"] == "date"]
    order_clause = f'"{date_cols[0]}" DESC' if date_cols else "(SELECT 1)"

    if id_candidates:
        # Pick the most unique key candidate
        best_key = max(id_candidates, key=lambda c: c["distinct_count"])["name"]
        key_dupes = distinct_rows - conn.execute(f'SELECT COUNT(DISTINCT "{best_key}") FROM {temp_stage_3}').fetchone()[0]

        if key_dupes > 0:
            dedupe_query = f"""
                CREATE OR REPLACE TABLE '{out_table}' AS 
                SELECT * FROM {temp_stage_3} 
                QUALIFY ROW_NUMBER() OVER (PARTITION BY "{best_key}" ORDER BY {order_clause}) = 1
            """
            conn.execute(dedupe_query)
            final_rows = conn.execute(f"SELECT COUNT(*) FROM '{out_table}'").fetchone()[0]
            cleaning_log.append({
                "step": "key_deduplication",
                "key_used": best_key,
                "rows_before": distinct_rows,
                "rows_after": final_rows,
                "dropped": distinct_rows - final_rows
            })
        else:
            conn.execute(f"CREATE OR REPLACE TABLE '{out_table}' AS SELECT * FROM {temp_stage_3}")
            final_rows = distinct_rows
            cleaning_log.append({"step": "key_deduplication", "detail": f"Unique key '{best_key}' has zero duplicates"})
    else:
        conn.execute(f"CREATE OR REPLACE TABLE '{out_table}' AS SELECT * FROM {temp_stage_3}")
        final_rows = distinct_rows
        cleaning_log.append({"step": "key_deduplication", "detail": "Skipped: no unique-key column detected with high confidence"})

    # Cleanup temporary tables
    for tmp in (temp_stage_1, temp_stage_2, temp_stage_3):
        conn.execute(f"DROP TABLE IF EXISTS {tmp}")

    db._introspect()
    final_profile = profile_table(conn, out_table)

    catalog_entry = {
        "table_name": out_table,
        "source_table": source_table,
        "row_count": final_rows,
        "columns": final_profile["columns"],
        "roles": final_profile.get("roles", {}),
        "cleaning_log": cleaning_log
    }

    if not hasattr(db, "catalog"):
        db.catalog = {}
    db.catalog[out_table] = catalog_entry

    return catalog_entry
