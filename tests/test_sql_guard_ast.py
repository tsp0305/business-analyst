import pytest
from core.sql_guard import check_sql

def test_sql_guard_column_load_timestamp():
    schema = {"t": ["id", "load_timestamp", "payload"]}
    res = check_sql("SELECT load_timestamp, payload FROM t", schema)
    assert res["ok"], res.get("error")
    assert "LIMIT 1000" in res["sql_rewritten"].upper()

def test_sql_guard_select_aliases_in_groupby_orderby():
    schema = {"t": ["region", "x"]}
    res = check_sql("SELECT region, SUM(x) AS total FROM t GROUP BY region ORDER BY total DESC", schema)
    assert res["ok"], res.get("error")
    assert "LIMIT 1000" in res["sql_rewritten"].upper()

def test_sql_guard_cte_support():
    schema = {"orders": ["id", "amount", "customer_id"]}
    query = """
    WITH high_value AS (
        SELECT customer_id, SUM(amount) AS total_spent
        FROM orders
        GROUP BY customer_id
    )
    SELECT customer_id, total_spent
    FROM high_value
    ORDER BY total_spent DESC
    """
    res = check_sql(query, schema)
    assert res["ok"], res.get("error")

def test_sql_guard_unknown_table():
    schema = {"users": ["id", "name"]}
    res = check_sql("SELECT id FROM non_existent_table", schema)
    assert not res["ok"]
    assert "Unknown table" in res["error"]

def test_sql_guard_unknown_column_suggestion():
    schema = {"users": ["user_id", "email_address"]}
    res = check_sql("SELECT email_addr FROM users", schema)
    assert not res["ok"]
    assert "Unknown column" in res["error"]
    assert len(res["suggestions"]) > 0

def test_sql_guard_blocked_read_csv():
    schema = {"t": ["id"]}
    res = check_sql("SELECT * FROM read_csv('data.csv')", schema)
    assert not res["ok"]
    assert "Blocked" in res["error"] or "blocked" in res["error"].lower()

def test_sql_guard_blocked_read_parquet():
    schema = {"t": ["id"]}
    res = check_sql("SELECT * FROM read_parquet('data.parquet')", schema)
    assert not res["ok"]
    assert "Blocked" in res["error"] or "blocked" in res["error"].lower()

def test_sql_guard_blocked_read_json():
    schema = {"t": ["id"]}
    res = check_sql("SELECT * FROM read_json('data.json')", schema)
    assert not res["ok"]
    assert "Blocked" in res["error"] or "blocked" in res["error"].lower()

def test_sql_guard_blocked_drop():
    schema = {"users": ["id"]}
    res = check_sql("DROP TABLE users", schema)
    assert not res["ok"]

def test_sql_guard_blocked_multi_statement():
    schema = {"users": ["id"]}
    res = check_sql("SELECT id FROM users; SELECT id FROM users;", schema)
    assert not res["ok"]
    assert "Multiple statements" in res["error"]
