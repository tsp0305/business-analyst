import os
import re
import zipfile
import tempfile
import pandas as pd
from typing import Dict, Any, List, Union

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".json", ".parquet"}
MAX_ZIP_FILES = 100
MAX_ZIP_TOTAL_BYTES = 200 * 1024 * 1024  # 200 MB

def safe_slug(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    return slug if slug else "dataset"

def get_unique_table_name(db, base_slug: str) -> str:
    db._introspect()
    existing = [t.lower() for t in db.list_tables()]
    candidate = f"ds_{base_slug}"
    if candidate.lower() not in existing:
        return candidate
    
    idx = 1
    while f"{candidate}_{idx}".lower() in existing:
        idx += 1
    return f"{candidate}_{idx}"

def ingest_single_file(db, file_path: str, original_filename: str = None) -> List[Dict[str, Any]]:
    """
    Ingest a single tabular file (.csv, .tsv, .json, .parquet, .xlsx).
    Returns list of accepted or skipped records.
    """
    filename = original_filename or os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return [{"status": "skipped", "filename": filename, "reason": f"unsupported extension: {ext}"}]

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return [{"status": "skipped", "filename": filename, "reason": "empty file (0 bytes)"}]

    slug = safe_slug(filename)
    results = []

    if ext == ".xlsx":
        try:
            excel_data = pd.read_excel(file_path, sheet_name=None)
            if not excel_data:
                return [{"status": "skipped", "filename": filename, "reason": "empty workbook (no sheets)"}]

            for sheet_name, sheet_df in excel_data.items():
                sheet_filename = f"{filename} [{sheet_name}]"
                if sheet_df.empty or len(sheet_df.columns) == 0:
                    results.append({"status": "skipped", "filename": sheet_filename, "reason": "empty sheet (0 rows or columns)"})
                    continue

                sheet_slug = f"{slug}_{safe_slug(sheet_name)}"
                table_name = get_unique_table_name(db, sheet_slug)

                # Sanitize column names for DuckDB
                clean_cols = [re.sub(r"[^a-zA-Z0-9_]+", "_", str(c)).strip("_") or f"col_{i}" for i, c in enumerate(sheet_df.columns)]
                sheet_df.columns = clean_cols

                temp_view = f"temp_view_{safe_slug(table_name)}"
                db.conn.register(temp_view, sheet_df)
                db.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM {temp_view}")
                db.conn.unregister(temp_view)
                db._introspect()

                cols = db.schema.get(table_name, list(sheet_df.columns))
                row_count = len(sheet_df)
                results.append({
                    "status": "accepted",
                    "filename": sheet_filename,
                    "table_name": table_name,
                    "rows": row_count,
                    "columns": cols
                })
            return results
        except Exception as e:
            return [{"status": "skipped", "filename": filename, "reason": f"Excel read error: {e}"}]

    # Direct DuckDB reader
    table_name = get_unique_table_name(db, slug)
    safe_path = os.path.abspath(file_path).replace("\\", "/")

    try:
        if ext == ".csv":
            db.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{safe_path}', header=True)")
        elif ext == ".tsv":
            db.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{safe_path}', delim='\t', header=True)")
        elif ext == ".parquet":
            db.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{safe_path}')")
        elif ext == ".json":
            db.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_json_auto('{safe_path}')")

        db._introspect()
        row_count = db.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        if row_count == 0:
            db.conn.execute(f"DROP TABLE {table_name}")
            db._introspect()
            return [{"status": "skipped", "filename": filename, "reason": "empty dataset (0 rows)"}]

        cols = db.schema.get(table_name, [])
        return [{
            "status": "accepted",
            "filename": filename,
            "table_name": table_name,
            "rows": row_count,
            "columns": cols
        }]
    except Exception as e:
        # Cleanup partially created table if any
        try:
            db.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        except Exception:
            pass
        return [{"status": "skipped", "filename": filename, "reason": f"Ingestion error: {e}"}]

def ingest_zip_file(db, zip_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Safely unpacks and ingests a ZIP file with path traversal, extension,
    and cumulative size defenses.
    """
    manifest = {"accepted": [], "skipped": []}

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infolist = zf.infolist()

            if len(infolist) > MAX_ZIP_FILES:
                manifest["skipped"].append({"filename": os.path.basename(zip_path), "reason": f"too many files in zip (max {MAX_ZIP_FILES})"})
                return manifest

            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_ZIP_TOTAL_BYTES:
                manifest["skipped"].append({"filename": os.path.basename(zip_path), "reason": f"total uncompressed size exceeds limit (max {MAX_ZIP_TOTAL_BYTES // (1024*1024)}MB)"})
                return manifest

            with tempfile.TemporaryDirectory() as tmpdir:
                for info in infolist:
                    if info.is_dir():
                        continue

                    raw_name = info.filename
                    norm_path = raw_name.replace("\\", "/")

                    # Zip-slip traversal defense
                    if norm_path.startswith("/") or ".." in norm_path.split("/"):
                        manifest["skipped"].append({"filename": raw_name, "reason": "path traversal detected (zip-slip)"})
                        continue

                    # Hidden / system metadata defense
                    parts = norm_path.split("/")
                    if any(p.startswith(".") or p == "__MACOSX" for p in parts):
                        manifest["skipped"].append({"filename": raw_name, "reason": "hidden or system metadata file"})
                        continue

                    # Extension check
                    ext = os.path.splitext(norm_path)[1].lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        manifest["skipped"].append({"filename": raw_name, "reason": f"unsupported extension: {ext}"})
                        continue

                    # Safe extract
                    extracted_path = zf.extract(info, path=tmpdir)
                    items = ingest_single_file(db, extracted_path, original_filename=os.path.basename(norm_path))

                    for item in items:
                        if item["status"] == "accepted":
                            manifest["accepted"].append(item)
                        else:
                            manifest["skipped"].append(item)

    except Exception as e:
        manifest["skipped"].append({"filename": os.path.basename(zip_path), "reason": f"corrupted zip archive: {e}"})

    return manifest

def ingest_dataset(db, file_path_or_buffer: Union[str, Any], filename: str = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Main ingestion entrypoint. Accepts a file path or file-like buffer (.zip, .csv, .tsv, etc.)
    and returns a manifest with accepted and skipped entries.
    """
    manifest = {"accepted": [], "skipped": []}

    # If buffer or uploaded file object
    if hasattr(file_path_or_buffer, "read"):
        name = filename or getattr(file_path_or_buffer, "name", "upload.tmp")
        ext = os.path.splitext(name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            if hasattr(file_path_or_buffer, "getbuffer"):
                tmp.write(file_path_or_buffer.getbuffer())
            else:
                tmp.write(file_path_or_buffer.read())
            tmp_path = tmp.name

        try:
            if ext == ".zip":
                return ingest_zip_file(db, tmp_path)
            else:
                items = ingest_single_file(db, tmp_path, original_filename=name)
                for item in items:
                    if item["status"] == "accepted":
                        manifest["accepted"].append(item)
                    else:
                        manifest["skipped"].append(item)
                return manifest
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Local file path
    path = str(file_path_or_buffer)
    name = filename or os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if ext == ".zip":
        return ingest_zip_file(db, path)
    else:
        items = ingest_single_file(db, path, original_filename=name)
        for item in items:
            if item["status"] == "accepted":
                manifest["accepted"].append(item)
            else:
                manifest["skipped"].append(item)
        return manifest
