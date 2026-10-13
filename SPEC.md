You are a senior engineer. Build a complete Python project named "agentic-bi": a Customizable Agentic BI Business Analyst System with a Streamlit UI. Follow this specification exactly. Keep code simple, typed, commented and framework-free (no LangChain, LlamaIndex or CrewAI).

FIRST ACTIONS (before anything else):
1. Save this entire prompt verbatim as SPEC.md in the project root.
2. Create STATE.md and update it after every stage (stages done, files, test counts, open issues, next step). If a session ends early, I will restart you with: "Read SPEC.md and STATE.md and continue from the next stage."

=====================================================
A. TEST PROTOCOL (applies to EVERY stage, non-negotiable)
=====================================================
- Write tests BEFORE or alongside the code, never after.
- At the end of each stage run `pytest -q` and paste the FULL output. Never say "all tests pass" without pasted output.
- If anything fails: diagnose the root cause in 2-3 lines, fix the code (not the test, unless the test is wrong, and say why), rerun, repeat until green.
- Never delete, skip, xfail or weaken a test to get green.
- Never move to the next stage while any test is red.
- Use MockLLM only in place of the LLM, never to mock away the logic under test.
- End each stage with a STAGE REPORT: files created, tests passed/total, known gaps, and the exact command I can run to verify. Then update STATE.md.
- Live LLM calls cost money: use mock and replay modes for everything until the stages explicitly say to run live.

=====================================================
B. PROJECT SUMMARY
=====================================================
Traditional BI dashboards leave interpretation to the user. This system uses AI agents in two phases.

PHASE 1, Data Understanding (once per uploaded CSV): agents investigate why duplicates exist, what ambiguous columns mean, how attributes relate, and what ETL steps are needed. Outputs: Data Dictionary, Attribute Relationship Graph, ETL Plan. The user reviews and approves ETL steps. Nothing is modified silently.

PHASE 2, Business Analysis (per user-configured agent): the user configures analyst agents (Sales, Inventory, Marketing, etc.) with name, domain, goal, KPIs, permitted tools and output style. Each agent answers natural-language questions through an iterative plan -> act (tool call) -> observe -> reflect loop, drills into root causes, self-verifies numbers, and returns an evidence-based, quantified recommendation with a visible reasoning trace.

=====================================================
C. TECH STACK
=====================================================
Python 3.11, Streamlit, DuckDB, pandas, Plotly, statsmodels, sqlglot, pydantic v2, python-dotenv, PyYAML, pytest, tenacity (or hand-written retry). One LLM provider with native tool/function calling; read the API key and model name from .env; the provider must be swappable in core/llm.py. Include requirements.txt, .env.example, README.md.

=====================================================
D. REPOSITORY STRUCTURE
=====================================================
agentic-bi/
  app.py
  pages/ 1_Upload_and_Profile.py, 2_Review_Phase1.py, 3_Agent_Config.py, 4_Chat.py
  core/ llm.py, agent_loop.py, tools.py, guards.py, sql_guard.py, evidence.py, verifier.py, hitl.py, context.py, trace.py, memory.py, db.py, schemas.py
  phase1/ profiler.py, duplicate_agent.py, semantic_agent.py, relationship_agent.py, etl_planner_agent.py, orchestrator.py, etl_executor.py
  phase2/ agent_config.py, analyst_agent.py, report_formatter.py
  tools/ sql_tool.py, kpi_tool.py, trend_tool.py, anomaly_tool.py, forecast_tool.py, drilldown_tool.py, chart_tool.py
  evals/ generate_data.py, cases.yaml, run_evals.py, report.md (generated)
  tests/ (one test file per module group, plus integration tests)
  data/ (uploads, sample CSV, ground_truth.json, dictionary.json, relationships.json, etl_plan.json, agents.json, findings.json, traces/, llm_cache/)
  SPEC.md, STATE.md, requirements.txt, .env.example, README.md

=====================================================
E. AGENT HARNESS (core/)
=====================================================
Principle: the LLM only chooses the next action. The harness executes, validates, bounds and records everything. The harness must never crash on model or tool errors.

E1. core/llm.py
- Provider-agnostic LLMClient.next_action(messages, tools) returns one Action.
- Action is a Pydantic union: ToolCall(name, args, thought) | AskUser(question, options?) | FinalAnswer(payload).
- Retry with exponential backoff on transient errors; JSON-parse repair (exactly one re-ask on malformed output).
- Token and cost accounting per call.
- MockLLM: plays back a scripted list of Actions.
- Record/replay: cache responses keyed by a hash of the prompt in data/llm_cache/ so tests are deterministic and free.
- Mode via env/flag: LLM_MODE=mock|replay|live.

E2. core/agent_loop.py - RunController
- Inputs: system_prompt, ToolRegistry restricted to allowed_tools, RunBudget, ContextManager, EvidenceLedger, Tracer, LLMClient, optional output schema.
- RunBudget defaults: max_steps=8, max_tokens=60000, timeout_s=90, max_consecutive_errors=3, max_repair_rounds=1.
- Each step the model returns exactly one action: tool_call, ask_user or final_answer.
- Stop reasons: final | budget_exhausted | stalled | user_input_needed | fatal.
- On budget exhaustion or stall: force a final answer from the evidence gathered so far (one extra LLM call with tools disabled).
- Return RunResult(answer, trace, stop_reason, usage, verified).
- The system prompt requires every tool_call to include a short "thought" stating plan status and what was learned from the last observation.

E3. core/tools.py - ToolRegistry
- Tool = name, description, Pydantic args model (JSON schema generated from it), function, timeout_s, max_result_chars.
- Reject calls to tools outside the agent's allowed_tools (error observation, counted in metrics).
- Invalid args become an error observation.
- Catch ALL exceptions and timeouts; return {"error","hint"} as the observation so the model can self-correct.
- Compact large results to schema + top rows + aggregate stats within max_result_chars.

E4. core/sql_guard.py (sqlglot)
- Allow exactly one SELECT. Block DDL/DML, multiple statements, comments hiding statements, and file/extension functions (read_csv, read_parquet, COPY, ATTACH, INSTALL, LOAD, PRAGMA).
- Verify tables and columns against the live DuckDB schema; on unknown columns return closest valid names (difflib).
- Inject LIMIT (default 1000) if missing; enforce a query timeout.
- Return a structured result: ok, sql_rewritten, error, suggestions.

E5. core/guards.py
- Detect: identical tool+args repeated; no new evidence for 3 consecutive steps; plan oscillation (A-B-A-B).
- First occurrence: inject a corrective nudge into the next context. On recurrence: force finalization.

E6. core/evidence.py - EvidenceLedger
- Every successful tool result gets an ID (E1, E2, ...) storing tool, args, compact result, timestamp. Provides a compact index for context and lookup by ID.

E7. core/verifier.py
- Final-answer Pydantic schema: summary, findings[{claim, numbers[], evidence_ids[]}], root_cause, quantified_impact, recommendation, caveats[].
- Programmatic checks: every cited evidence_id exists; every number in each finding appears in (or is derivable by simple arithmetic such as difference, ratio, percent change from) the cited evidence, within a small tolerance.
- On failure: feed specific errors back for at most max_repair_rounds, then return the answer flagged verified=False with the failed checks listed.

E8. core/hitl.py
- ask_user pauses the run, serializes run state (messages, ledger, step counter), and resumes when the user replies (Streamlit session state). Also used for the ETL approval gate and Semantic Analyst escalation.

E9. core/context.py - ContextManager
- Each prompt = system prompt + Phase 1 dictionary and relationships (always) + thread memory + last 4 steps verbatim + short summaries of older steps + compact evidence ledger index. Enforce a token budget by dropping oldest summaries first.

E10. core/trace.py
- One JSONL file per run in data/traces/: run_id, step, thought, tool, args, result_summary, evidence_id, latency_ms, tokens, cost, stop_reason. The UI trace panel reads from it.

E11. core/db.py
- DuckDB wrapper: load CSV into an immutable raw table, schema introspection, guarded execute() that ALWAYS goes through sql_guard. Cleaned data goes into a separate table.

E12. core/memory.py
- Thread memory (recent queries, answers, last result context) so follow-ups like "now break that down by product category" or "draft this as a summary for my manager" are refinements. Optional persistence of findings to data/findings.json with recall and re-check of earlier conclusions.

=====================================================
F. PHASE 1 - DATA UNDERSTANDING
=====================================================
Every Phase 1 agent runs on RunController with its own system prompt, restricted tools (read-only SQL, profile lookups) and output schema.
- profiler.py: per-column dtype, null %, unique count, min/max, sample values, exact-duplicate row count, near-duplicate candidates.
- DuplicateInvestigator: detects exact and near duplicates, forms hypotheses (repeated ingestion, join fan-out, entity duplication), tests each with SQL (e.g. duplicates cluster by load timestamp, differ only in a key), outputs likely cause plus proposed dedup key.
- SemanticAnalyst: infers meaning of column names and abbreviations from names, value patterns and statistics; escalates via ask_user when genuinely ambiguous. Web lookup is optional and stubbed behind a flag; no network required.
- RelationshipDiscovery: functional dependencies (A -> B tested via SQL), derived fields (e.g. revenue = qty * price), correlations, hierarchies, referential links. Output: graph (nodes, edges with type and confidence).
- ETLPlanner: JSON list of steps {id, description, rationale, confidence, action:{type: sql|pandas, code}}. Never modifies data.
- orchestrator.py: runs Duplicate -> Semantic -> Relationship -> ETL Planner, shares context, writes data/dictionary.json, relationships.json, etl_plan.json.
- etl_executor.py: applies ONLY user-approved steps on a copy, producing the cleaned table. Log row counts before/after per step. Support undo by rebuilding from raw.

=====================================================
G. PHASE 2 - BUSINESS ANALYSIS
=====================================================
- agent_config.py: AgentConfig(name, domain, goal, kpis[], allowed_tools[], output_style "analyst"|"executive"); persist to data/agents.json; presets for Sales, Inventory, Marketing with genuinely different tools and KPIs.
- analyst_agent.py: builds a RunController whose system prompt includes the config AND the Phase 1 dictionary and relationships, and whose registry contains ONLY allowed_tools (structural specialization, not just prompt wording).
- Required behavior (in the system prompt AND checked in evals): plan then revise from evidence; concrete tool arguments; automatic root-cause drill-down when results are surprising (e.g. region -> category within region); self-verification of key numbers against a simpler aggregate; ask_user when the query is ambiguous; final answer satisfies the verifier schema and cites evidence IDs.
- report_formatter.py: detailed analyst view (all findings, evidence, trace) or executive summary (3-5 lines, headline number, one recommendation), per output_style or UI toggle.

Tools (tools/, each with Pydantic args model, compact return, registered in ToolRegistry, DB access via core/db.py only):
- run_sql(query); compute_kpi(kpi, filters, period); trend_analysis(metric, grain, periods); detect_anomalies(metric, grain, method=zscore|iqr); forecast(metric, horizon, grain) via statsmodels returning point forecast and interval; drilldown_by_dimension(metric, period_a, period_b, dimensions[]) ranking contribution to change; make_chart(spec) saving Plotly JSON and returning a chart ID.

=====================================================
H. UI (Streamlit multipage)
=====================================================
(a) Upload & Profile: upload CSV, profile table, duplicate summary.
(b) Review Phase 1: run orchestrator with progress; editable Data Dictionary; Relationship Graph; ETL Plan with per-step Approve/Reject and rationale; "Apply approved steps" with before/after row counts; inline ask_user prompts.
(c) Agent Config: create/edit/delete agents via form (name, domain, goal, KPIs, tool multiselect, output style) plus presets.
(d) Chat: select an agent; chat input; answer with charts; analyst/executive toggle; expandable "Reasoning trace" (steps, tools, args, evidence IDs, latency); verified/unverified badge; stop reason; ask_user pause/resume; follow-ups via thread memory. Include an interactive KPI dashboard section (KPI cards, trend charts, anomaly markers) for the selected agent.
Keep page files thin; put testable logic in separate functions.

=====================================================
I. EVALS
=====================================================
evals/generate_data.py: SEEDED generator writing data/sample_sales.csv and data/ground_truth.json with planted facts:
- at least 12 months of daily data, 4 regions, 5 categories; rev_amt = qty_ord * unit_price;
- about 4% of rows duplicated via repeated ingestion (second load timestamp);
- a -22% sales drop in region "South" in the last month, driven by category "Electronics";
- one day with a 5x revenue spike;
- ambiguous columns qty_ord, cust_id, rev_amt, prod_cat, ord_dt with known meanings;
- ground_truth.json also records the exact true drop %, dedup key and spike date.

evals/cases.yaml + evals/run_evals.py with --llm=mock|replay|live. Cases (programmatic pass/fail against ground_truth.json, NOT an LLM judge):
1. "Why did sales decrease last month?" names South + Electronics, stated drop within +/-2 percentage points of truth.
2. Duplicate investigation identifies repeated ingestion and a correct dedup key.
3. Data dictionary matches >=90% of ground-truth meanings.
4. Vague query "how are we doing?" triggers ask_user.
5. An Inventory agent never calls a tool outside its allowed_tools.
6. A prompt-injected DROP TABLE attempt is blocked and the run continues.
7. The loop guard triggers on a scripted repeating MockLLM.
8. The verifier flags a fabricated number.
Per-case metrics: success, steps, tool error rate, hallucinated-column rate, verifier pass rate, tokens, cost, latency, stop reason. Write evals/report.md. Mock and replay must run with no API key.

=====================================================
J. NON-FUNCTIONAL REQUIREMENTS
=====================================================
- No silent data modification anywhere; the raw table is immutable.
- Secrets only from .env; never log API keys.
- Every agent run produces a trace file.
- Type hints and docstrings on public functions; small functions.
- `streamlit run app.py` works end to end on the sample dataset in mock/replay mode with no API key, and in live mode with a key.
- README: mermaid architecture diagram, setup, running app/tests/evals, adding a tool, adding an analyst agent, known limitations.

=====================================================
K. STAGES (execute in order; follow the TEST PROTOCOL at every stage)
=====================================================
STAGE 0 - PLAN (no code). Produce the full file tree, an implementation plan for stages 1-9 with public interfaces (signatures) and the exact tests per stage, plus assumptions and risks. Ask me ONE question only: which LLM provider to implement (Gemini or Claude API). Then STOP and wait for my approval.

STAGE 1 - Harness core. Build the scaffold (requirements, .env.example, pytest config) and core/schemas.py, llm.py (MockLLM, record/replay), tools.py, sql_guard.py, db.py.
Tests: sql_guard (allowed SELECT; blocked DROP/DELETE/INSERT/UPDATE; multiple statements; read_csv/COPY/ATTACH/PRAGMA; comment-hidden second statement; unknown column with suggestions; LIMIT injection). Tool registry (disallowed tool rejected; invalid args; raising tool returns {"error","hint"}; timeout; result compaction; schema generated from Pydantic). LLM (MockLLM order; one repair on malformed JSON; record then replay identical; backoff on transient error). DB (CSV loads to raw table; raw table not modifiable via execute(); schema introspection).

STAGE 2 - Harness remaining. Build evidence.py, guards.py, verifier.py, context.py, trace.py, memory.py, hitl.py, agent_loop.py.
Tests (MockLLM scripted): loop guards (repeat -> nudge -> forced finalize; no new evidence for 3 steps; A-B-A-B). Budgets (max_steps, max_tokens, timeout_s, max_consecutive_errors each stop the run, still return a forced final answer, never raise). Verifier (fabricated number flagged; derived difference/ratio/percent-change accepted; missing evidence_id flagged; one repair round then verified=False). Agent loop (happy path with evidence IDs E1..En; ask_user pause and resume from serialized state; disallowed tool rejected and run continues). Trace/context (one JSONL per run with required fields; dictionary always included; last 4 steps verbatim; token budget respected). Finish with one integration test covering tool call, error recovery, loop guard and a verified final answer.

STAGE 3 - Data generator. Build evals/generate_data.py and generate the sample data and ground truth.
Tests: same seed gives the same file; duplicate rate 4% +/-0.5; South Electronics last month down 22% +/-1 vs prior month, computed independently from the CSV; exactly one day above 4x median daily revenue; rev_amt = qty_ord * unit_price on non-spike rows; ground_truth.json values match values recomputed from the data.

STAGE 4 - Analytics tools. Build all of tools/ and register them.
Tests on the sample data in DuckDB: compute_kpi matches pandas; trend_analysis last vs prior month gives the correct percent change; detect_anomalies (zscore and iqr) flags the planted spike date; drilldown_by_dimension ranks South first and, inside South, Electronics first; forecast returns a horizon-length series with intervals and returns an error observation (not an exception) on short series; make_chart saves valid Plotly JSON and returns an ID; every tool returns error observations on bad args and respects max_result_chars; run_sql blocks DROP TABLE but allows SELECT.

STAGE 5 - Phase 1. Build profiler, the four agents, orchestrator, etl_executor.
Tests: profiler stats correct on sample data. etl_executor (only approved steps applied; rejected not applied; raw table unchanged; before/after counts logged; undo rebuilds from raw). Each agent runs end to end with scripted MockLLM and yields schema-valid output. Orchestrator in replay mode writes schema-valid dictionary.json, relationships.json, etl_plan.json.
Then, if an API key is present, run the orchestrator LIVE on the sample data and print a table of its output vs ground_truth.json (duplicate cause and dedup key, % dictionary meanings matched, whether rev_amt = qty_ord * unit_price was discovered). If below target, tune prompts, rerun, and show before/after. Record live responses into the replay cache.

STAGE 6 - Phase 2. Build agent_config, analyst_agent, report_formatter, presets.
Tests: config validation, save/load, presets; the registry contains only allowed_tools; an Inventory agent calling a Sales-only tool is rejected; the system prompt contains config + dictionary + relationships; analyst view contains all findings, evidence IDs and trace while executive view is 3-5 lines with a headline number and one recommendation; a follow-up reuses thread memory without restarting the investigation; saved findings can be recalled.

STAGE 7 - Eval runner. Build cases.yaml and run_evals.py.
Tests: a deliberately wrong scripted answer fails case 1; a correct scripted answer passes it; cases 5-8 pass in mock mode.
Then run `python evals/run_evals.py --llm=mock`, then `--llm=replay`; fix failures. If a key exists, run `--llm=live`, show evals/report.md, and for each failed case diagnose from the trace whether the cause is the prompt, a tool or the harness; fix, rerun, show before/after; record responses for replay.

STAGE 8 - UI. Build app.py and pages/.
Tests with streamlit.testing.v1.AppTest: each page loads without exceptions; uploading the sample CSV shows the profile table; the ETL review page shows Approve/Reject per step and Apply only applies approved steps; the config form saves to agents.json; chat with MockLLM shows an answer, a trace and the badge; the ask_user flow pauses, shows the question, and resumes on answer. Then launch `streamlit run app.py`, confirm no startup errors, and list manual click-through steps for me.

STAGE 9 - Final. Write README.md. Then run, pasting every output: `pytest -q` (full suite); evals in mock, replay, and live (if a key is present). Run "Why did sales decrease last month?" with the Sales Analyst agent on the sample data and show the full trace (every step, tool, args, evidence ID) and the final verified answer. Produce a FINAL REPORT: test counts, eval table, anything unfinished, and the top 5 improvements ranked.

=====================================================
L. RULES WHEN THINGS GO WRONG
=====================================================
- Red test: root-cause in 2-3 lines, fix the code, rerun the full suite, do not touch unrelated modules.
- Bad live agent behavior: read the trace in data/traces/, classify the cause (prompt, tool design, context, harness), apply the smallest fix, add a regression test or eval case, rerun evals, show before/after metrics.
- Spec drift: re-read the relevant section, list each requirement as done/partial/missing with its file, and implement only the gaps with tests.
- If a requirement is ambiguous, state your assumption in the plan instead of asking, except for the LLM provider question in Stage 0.
- Do not add features beyond this spec. If time is short, cut in this order: web lookup, KPI dashboard section, forecast tool. Never cut the harness, tests or evals.