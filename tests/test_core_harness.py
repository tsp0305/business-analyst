import pytest
from core.sql_guard import check_sql
from core.tools import ToolRegistry, Tool
from core.db import DBContext
from core.llm import LLMClient, MockLLM, ToolCall
from pydantic import BaseModel, Field

# --- SQL Guard Tests ---
def test_sql_guard_allowed_select():
    schema = {"users": ["id", "name"]}
    res = check_sql("SELECT id FROM users", schema)
    assert res["ok"]
    assert "LIMIT" in res["sql_rewritten"].upper()

def test_sql_guard_blocked_dml():
    schema = {"users": ["id", "name"]}
    res = check_sql("DROP TABLE users", schema)
    assert not res["ok"]
    assert "DROP" in res["error"].upper() or "blocked" in res["error"].lower()
    
    res2 = check_sql("INSERT INTO users VALUES (1, 'a')", schema)
    assert not res2["ok"]

def test_sql_guard_multiple_statements():
    schema = {"users": ["id", "name"]}
    res = check_sql("SELECT id FROM users; DROP TABLE users", schema)
    assert not res["ok"]
    assert "multiple" in res["error"].lower()

def test_sql_guard_blocked_file_funcs():
    schema = {"users": ["id", "name"]}
    res = check_sql("SELECT * FROM read_csv('data.csv')", schema)
    assert not res["ok"]
    assert "read_csv" in res["error"].lower() or "blocked" in res["error"].lower()

def test_sql_guard_comment_hidden_statement():
    schema = {"users": ["id", "name"]}
    res = check_sql("SELECT id FROM users; -- DROP TABLE users\nSELECT name FROM users", schema)
    assert not res["ok"]
    assert "multiple" in res["error"].lower()

def test_sql_guard_unknown_column():
    schema = {"users": ["id", "user_name"]}
    res = check_sql("SELECT name FROM users", schema)
    assert not res["ok"]
    assert "user_name" in res["suggestions"][0]

def test_sql_guard_limit_injection():
    schema = {"users": ["id"]}
    res = check_sql("SELECT id FROM users", schema)
    assert "LIMIT 1000" in res["sql_rewritten"].upper()
    
    res2 = check_sql("SELECT id FROM users LIMIT 10", schema)
    assert "LIMIT 10" in res2["sql_rewritten"].upper()
    assert "LIMIT 1000" not in res2["sql_rewritten"].upper()

# --- Tool Registry Tests ---
class DummyArgs(BaseModel):
    val: int

def dummy_func(args):
    if args["val"] < 0:
        raise ValueError("negative")
    return {"result": args["val"] * 2}

@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(Tool(
        name="dummy",
        description="A dummy tool",
        args_schema=DummyArgs,
        func=dummy_func
    ))
    return reg

def test_tool_registry_disallowed(registry):
    res = registry.execute("unknown_tool", {}, allowed_tools=["dummy"])
    assert "error" in res
    assert "unknown_tool" in res["error"]

def test_tool_registry_invalid_args(registry):
    res = registry.execute("dummy", {"val": "not an int"}, allowed_tools=["dummy"])
    assert "error" in res
    assert "hint" in res

def test_tool_registry_raising_tool(registry):
    res = registry.execute("dummy", {"val": -1}, allowed_tools=["dummy"])
    assert "error" in res
    assert "negative" in res["error"]
    assert "hint" in res

def test_tool_registry_timeout():
    import time
    def slow_func(args):
        time.sleep(1)
        return {}
    
    reg = ToolRegistry()
    reg.register(Tool(name="slow", description="Slow", args_schema=DummyArgs, func=slow_func, timeout_s=0.1))
    res = reg.execute("slow", {"val": 1}, allowed_tools=["slow"])
    assert "error" in res
    assert "timeout" in res["error"].lower()

def test_tool_registry_compaction():
    def big_func(args):
        return {"data": "x" * 2000}
    reg = ToolRegistry()
    reg.register(Tool(name="big", description="Big", args_schema=DummyArgs, func=big_func, max_result_chars=100))
    res = reg.execute("big", {"val": 1}, allowed_tools=["big"])
    assert len(str(res)) <= 150 # allow some overhead
    assert "compacted" in str(res).lower() or len(res.get("data", "")) < 2000

def test_tool_registry_schema():
    reg = ToolRegistry()
    reg.register(Tool(name="dummy", description="Dummy", args_schema=DummyArgs, func=dummy_func))
    schema = reg.get_tool_schema("dummy")
    assert "properties" in schema
    assert "val" in schema["properties"]

# --- LLM Tests ---
def test_llm_mock_order():
    mock = MockLLM(script=[ToolCall(name="dummy", args={"val":1}, thought="thought 1")])
    res = mock.next_action([], [])
    assert res.name == "dummy"

def test_llm_parse_repair():
    class BadLLM(LLMClient):
        def _call_api(self, prompt, tools):
            if "REPAIR" not in str(prompt):
                return '{"invalid json'
            return '{"name": "dummy", "args": {}, "thought": "fixed"}'
    
    llm = BadLLM()
    # It should repair and return a toolcall
    res = llm.next_action([], [])
    assert getattr(res, 'name', None) == "dummy"

def test_llm_record_replay(tmp_path):
    # record
    mock = MockLLM(script=[ToolCall(name="t1", args={}, thought="1")])
    llm = LLMClient(mode="record", cache_dir=str(tmp_path), provider_client=mock)
    res1 = llm.next_action([{"role":"user", "content":"test"}], [])
    
    # replay
    llm2 = LLMClient(mode="replay", cache_dir=str(tmp_path))
    res2 = llm2.next_action([{"role":"user", "content":"test"}], [])
    assert res1 == res2

def test_llm_backoff_on_transient():
    class FailOnceLLM(LLMClient):
        calls = 0
        def _call_api(self, prompt, tools):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("transient")
            return '{"name": "dummy", "args": {}, "thought": "ok"}'
    
    llm = FailOnceLLM()
    res = llm.next_action([], [])
    assert getattr(res, 'name', None) == "dummy"
    assert llm.calls == 2

# --- DB Tests ---
def test_db_csv_load(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,val\n1,10\n2,20")
    
    db = DBContext()
    db.load_csv(str(csv_file), "raw_data")
    
    schema = db.get_schema()
    assert "raw_data" in schema
    assert "id" in schema["raw_data"]
    
def test_db_immutable_raw(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,val\n1,10")
    
    db = DBContext()
    db.load_csv(str(csv_file), "raw_data")
    
    # executing arbitrary queries goes through sql_guard, which blocks INSERT
    res = db.execute("INSERT INTO raw_data VALUES (2, 20)")
    assert "error" in res
    assert "blocked" in res["error"].lower() or "not ok" in res["error"].lower()

def test_db_schema_introspection(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,val\n1,10")
    
    db = DBContext()
    db.load_csv(str(csv_file), "my_table")
    
    schema = db.get_schema()
    assert "my_table" in schema
    assert "id" in schema["my_table"]
    assert "val" in schema["my_table"]
