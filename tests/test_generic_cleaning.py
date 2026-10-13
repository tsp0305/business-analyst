import pytest
from core.db import DBContext
from core.ingest import ingest_dataset
from core.profiler import clean_and_profile_dataset

@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test_cleaning.duckdb")
    db_ctx = DBContext(db_path=db_file)
    yield db_ctx
    db_ctx.close()

def test_cleaning_fixture_sales(db, tmp_path):
    csv_file = tmp_path / "retail_tx.csv"
    csv_file.write_text("""transaction_id,sold_at,store_branch,total_price,units
TX101,2023-01-15, Downtown ,150.50,2
TX102,2023-01-16,Uptown,75.00,1
TX103,2023-01-17,NULL,200.00,N/A
TX101,2023-01-15, Downtown ,150.50,2
""")
    manifest = ingest_dataset(db, str(csv_file))
    src_table = manifest["accepted"][0]["table_name"]

    catalog = clean_and_profile_dataset(db, src_table)
    clean_table = catalog["table_name"]
    assert clean_table.startswith("clean_")

    # Exact duplicate was dropped (4 rows -> 3 rows)
    assert catalog["row_count"] == 3

    roles = {c["name"]: c["role"] for c in catalog["columns"]}
    assert roles["transaction_id"] == "id"
    assert roles["sold_at"] == "date"
    assert roles["total_price"] == "measure"

    # Check trimmed text and sentinel NULL replacement
    rows = db.conn.execute(f"SELECT store_branch FROM {clean_table} WHERE transaction_id='TX101'").fetchall()
    assert rows[0][0] == "Downtown"

    null_row = db.conn.execute(f"SELECT store_branch FROM {clean_table} WHERE transaction_id='TX103'").fetchall()
    assert null_row[0][0] is None

def test_cleaning_fixture_hr(db, tmp_path):
    csv_file = tmp_path / "hr_records.csv"
    csv_file.write_text("""emp_code,hired_date,department_name,salary_amount,is_active
E001,2021-03-01,Engineering,110000,1
E002,2021-06-15,Marketing,85000,1
E003,2022-01-10,Engineering,125000,0
E004,2022-05-20,Finance,92000,1
E002,2021-06-15,Marketing,85000,1
""")
    manifest = ingest_dataset(db, str(csv_file))
    src_table = manifest["accepted"][0]["table_name"]

    catalog = clean_and_profile_dataset(db, src_table)
    assert catalog["row_count"] == 4  # dropped duplicate E002

    roles = {c["name"]: c["role"] for c in catalog["columns"]}
    assert roles["emp_code"] == "id"
    assert roles["hired_date"] == "date"
    assert roles["salary_amount"] == "measure"
    assert roles["department_name"] == "dimension"

def test_cleaning_fixture_web_events(db, tmp_path):
    csv_file = tmp_path / "analytics_events.csv"
    csv_file.write_text("""event_uuid,event_time,page_path,duration_sec,referrer
EV-1,2024-02-01 10:00:00,/home,15,google
EV-2,2024-02-01 10:02:00,/pricing,45,bing
EV-3,2024-02-01 10:05:00,/docs,120,
EV-4,2024-02-01 10:06:00,/blog,30,google
""")
    manifest = ingest_dataset(db, str(csv_file))
    src_table = manifest["accepted"][0]["table_name"]

    catalog = clean_and_profile_dataset(db, src_table)
    assert catalog["row_count"] == 4

    roles = {c["name"]: c["role"] for c in catalog["columns"]}
    assert roles["event_uuid"] == "id"
    assert roles["event_time"] == "date"
    assert roles["duration_sec"] == "measure"

    # Empty string referrer became NULL
    ref_row = db.conn.execute(f"SELECT referrer FROM {catalog['table_name']} WHERE event_uuid='EV-3'").fetchall()
    assert ref_row[0][0] is None
