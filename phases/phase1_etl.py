import os
from core.db import DBContext
from core.ingest import ingest_dataset
from core.profiler import clean_and_profile_dataset

def run_phase_1(arg1=None, arg2=None, out_table: str = None, db: DBContext = None, **kwargs) -> dict:
    """
    Deterministic Phase 1 ETL Pipeline:
    Ingests source data (if not already in DuckDB), profiles columns,
    infers roles, applies generic sanitization, exact deduplication, and
    high-confidence key deduplication.
    
    No LLM code execution is used.
    """
    # Flexible argument parsing for backwards compatibility
    if isinstance(arg1, DBContext):
        target_db = arg1
        source_target = arg2
    else:
        # arg1 might be llm_client, arg2 is path or table
        target_db = db or kwargs.get("db") or DBContext()
        source_target = arg2 or kwargs.get("csv_path") or kwargs.get("source_table")

    if not source_target:
        return {"success": False, "error": "No source dataset provided", "row_count": 0}

    source_table = None

    # Check if source_target is an existing table in DB
    if target_db.table_exists(source_target):
        source_table = source_target
    elif os.path.exists(source_target):
        # Ingest file into DuckDB
        manifest = ingest_dataset(target_db, source_target)
        if manifest["accepted"]:
            source_table = manifest["accepted"][0]["table_name"]
        else:
            reason = manifest["skipped"][0]["reason"] if manifest["skipped"] else "Unknown ingest failure"
            return {"success": False, "error": f"Ingestion failed: {reason}", "row_count": 0}
    else:
        # Check if table without prefix exists
        for t in target_db.list_tables():
            if t.lower() == source_target.lower():
                source_table = t
                break

    if not source_table:
        return {"success": False, "error": f"Table or file '{source_target}' not found", "row_count": 0}

    # Clean and profile
    catalog_entry = clean_and_profile_dataset(target_db, source_table, clean_table_name=out_table)

    return {
        "success": True,
        "table_name": catalog_entry["table_name"],
        "row_count": catalog_entry["row_count"],
        "catalog_entry": catalog_entry,
        "cleaning_details": catalog_entry["cleaning_log"],
        "columns": [c["name"] for c in catalog_entry["columns"]],
        "trace": []
    }
