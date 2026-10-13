import pytest
import os
import zipfile
import json
import pandas as pd
from core.db import DBContext
from core.ingest import ingest_dataset

@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.duckdb")
    db = DBContext(db_path=db_file)
    yield db
    db.close()

def test_ingest_two_datasets_coexist(test_db, tmp_path):
    f1 = tmp_path / "sales.csv"
    f1.write_text("id,amount\n1,100\n2,200\n")

    f2 = tmp_path / "sales.csv"  # same base name

    m1 = ingest_dataset(test_db, str(f1), filename="sales.csv")
    assert len(m1["accepted"]) == 1
    t1 = m1["accepted"][0]["table_name"]
    assert t1 == "ds_sales"
    assert m1["accepted"][0]["rows"] == 2

    # Second file with same base name should get numeric suffix ds_sales_1
    m2 = ingest_dataset(test_db, str(f2), filename="sales.csv")
    assert len(m2["accepted"]) == 1
    t2 = m2["accepted"][0]["table_name"]
    assert t2 == "ds_sales_1"
    assert m2["accepted"][0]["rows"] == 2

    # Both tables must exist in DuckDB
    tables = test_db.list_tables()
    assert "ds_sales" in tables
    assert "ds_sales_1" in tables

def test_ingest_empty_file(test_db, tmp_path):
    empty_f = tmp_path / "empty.csv"
    empty_f.write_text("")

    manifest = ingest_dataset(test_db, str(empty_f))
    assert len(manifest["accepted"]) == 0
    assert len(manifest["skipped"]) == 1
    assert "empty file" in manifest["skipped"][0]["reason"]

def test_ingest_zip_mixed_formats_and_safety(test_db, tmp_path):
    zip_path = tmp_path / "mixed.zip"

    # Prepare files in a zip:
    # 1. valid csv
    # 2. valid json
    # 3. zip-slip path traversal attempt
    # 4. macOS metadata file
    # 5. unsupported .txt file

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("customers.csv", "cid,name\n10,Alice\n20,Bob\n")
        zf.writestr("products.json", json.dumps([{"pid": 1, "pname": "Widget"}, {"pid": 2, "pname": "Gadget"}]))
        zf.writestr("../traversal.csv", "evil,data\n1,2\n")
        zf.writestr("__MACOSX/._customers.csv", "junk")
        zf.writestr("notes.txt", "Some text note")

    manifest = ingest_dataset(test_db, str(zip_path))

    # Accepted: customers.csv and products.json
    accepted_files = [item["filename"] for item in manifest["accepted"]]
    assert "customers.csv" in accepted_files
    assert "products.json" in accepted_files
    assert len(manifest["accepted"]) == 2

    # Skipped: traversal, __MACOSX, and .txt
    skipped_reasons = {item["filename"]: item["reason"] for item in manifest["skipped"]}
    assert any("path traversal" in r for f, r in skipped_reasons.items() if "traversal" in f)
    assert any("metadata" in r for f, r in skipped_reasons.items() if "__MACOSX" in f)
    assert any("unsupported" in r for f, r in skipped_reasons.items() if "notes.txt" in f)

    # Tables exist in DuckDB
    tables = test_db.list_tables()
    assert "ds_customers" in tables
    assert "ds_products" in tables
