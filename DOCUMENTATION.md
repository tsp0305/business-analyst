# Agentic BI Business Analyst — Functional Documentation

A comprehensive architectural and functional reference for the **Universal Agentic BI Business Analyst System**.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project Structure](#2-project-structure)
3. [UI Architecture — Multipage Streamlit App](#3-ui-architecture--multipage-streamlit-app)
4. [Shared Module (`utils/shared.py`)](#4-shared-module-utilssharedpy)
5. [Universal Ingestion Pipeline (`core/ingest.py`)](#5-universal-ingestion-pipeline-coreingestpy)
6. [Data Profiling, Cleaning & Cataloging](#6-data-profiling-cleaning--cataloging)
7. [Security & AST SQL Guard (`core/sql_guard.py`)](#7-security--ast-sql-guard-coresql_guardpy)
8. [Core Agentic Loop & Prompt Grounding](#8-core-agentic-loop--prompt-grounding)
9. [Analytical Tools (`tools/`)](#9-analytical-tools-tools)
10. [Anti-Hallucination Verifier (`core/verifier.py`)](#10-anti-hallucination-verifier-coreverifierpy)
11. [Zero-Cost Offline Planner (`phases/planner.py`)](#11-zero-cost-offline-planner-phasesplannerpy)
12. [Known CSS Fix — Expander Arrow Overlap](#12-known-css-fix--expander-arrow-overlap)
13. [Testing & Quality Assurance](#13-testing--quality-assurance)

---

## 1. System Overview

Traditional BI dashboards require manual analyst configuration while generic LLM chatbots hallucinate statistical numbers or execute unsafe SQL. This system eliminates both problems:

- **Universal Schema Independence** — works on any tabular dataset or multi-file ZIP archive with no hardcoded column names or assumptions.
- **Framework-Free** — built with Python 3.11+, DuckDB, Pandas, and Plotly only. No LangChain, LlamaIndex, or CrewAI.
- **Verifiable Numbers** — every numerical claim is cross-checked against an immutable `EvidenceLedger` before reaching the user.
- **AST SQL Security** — all queries parsed with SQLGlot into abstract syntax trees, guaranteeing read-only execution and blocking injection vectors.
- **Dual Execution Engine** — live Gemini AI mode when an API key is present; zero-cost offline schema planner when not.

---

## 2. Project Structure

```
BI-analyst/
│
├── app.py                          # Entry point — Home / landing page
│
├── pages/                          # Streamlit multipage routing
│   ├── 2_BI_Analyst_Chat.py        # Conversational BI chat + mini live dashboard
│   ├── 3_Data_Cleaning_Profiling.py# Dataset profiling, column roles, quality tabs
│   ├── 4_BI_Analytics_Dashboard.py # Full-width KPI dashboard with 6 live charts
│   ├── 5_SQL_Data_Explorer.py      # Interactive DuckDB SQL console + auto-viz
│   └── 6_Settings.py               # API keys, model config, system info
│
├── utils/
│   └── shared.py                   # CSS, session state, sidebar, chart helpers,
│                                   # page_header(), render_sidebar(), all chart fns
│
├── core/                           # Agent framework
│   ├── agent_loop.py               # RunController — budget, steps, error recovery
│   ├── context.py                  # Schema catalog → prompt grounding
│   ├── db.py                       # DuckDB context & schema manager
│   ├── evidence.py                 # EvidenceLedger (E1, E2, …)
│   ├── guards.py                   # Anti-oscillation & stall guards
│   ├── hitl.py                     # Human-in-the-loop pause/resume
│   ├── ingest.py                   # Universal ingestion engine
│   ├── llm.py                      # LLMClient + GeminiProviderClient
│   ├── memory.py                   # Thread memory for follow-up context
│   ├── profiler.py                 # Column profiler, role inferrer, clean catalog
│   ├── schemas.py                  # Pydantic schemas (ToolCall, AskUser, FinalAnswer)
│   ├── sql_guard.py                # AST-based SQLGlot validator
│   ├── tools.py                    # Tool registry + error boundaries
│   ├── trace.py                    # JSONL audit trace logger
│   └── verifier.py                 # Number-to-evidence cross-checker
│
├── phases/
│   ├── phase1_etl.py               # Phase 1: clean, deduplicate, catalog
│   ├── phase2_analysis.py          # Phase 2: agentic question answering
│   └── planner.py                  # Zero-cost offline schema planner
│
├── tools/                          # Analytical tool modules
│   ├── base_tool.py                # Identifier validation, filters, timeout guard
│   ├── anomaly_tool.py             # Outlier detection (z-score / IQR)
│   ├── chart_tool.py               # Plotly chart creation & serialization
│   ├── drilldown_tool.py           # Dimensional ranking & drilldown
│   ├── forecast_tool.py            # Trend forecasting with confidence intervals
│   ├── kpi_tool.py                 # Aggregated KPI computation
│   ├── python_tool.py              # Sandboxed Python expression evaluator
│   ├── sql_tool.py                 # AST-guarded raw SQL executor
│   └── trend_tool.py               # Period-over-period comparative analytics
│
├── evals/
│   ├── generate_data.py            # Synthetic sales dataset fixture generator
│   └── run_eval.py                 # Automated benchmark evaluator
│
├── tests/                          # Pytest suite (90 tests, 100% offline)
│   ├── test_analytics_tools.py
│   ├── test_core_advanced.py
│   ├── test_core_harness.py
│   ├── test_data_generator.py
│   ├── test_eval_runner.py
│   ├── test_generic_cleaning.py
│   ├── test_generic_tools.py
│   ├── test_ingest.py
│   ├── test_offline_planner.py
│   ├── test_phase1.py
│   ├── test_phase2.py
│   ├── test_phase2_grounding.py
│   ├── test_sql_guard_ast.py
│   ├── test_ui.py                  # Multipage smoke tests (AppTest)
│   └── test_verifier_comprehensive.py
│
├── data/
│   ├── charts/                     # Serialized Plotly chart JSON files
│   ├── llm_cache/                  # LLM record/replay cache
│   ├── state/                      # HITL pause/resume state files
│   ├── traces/                     # JSONL agent execution traces
│   ├── uploads/                    # Uploaded user files (runtime)
│   ├── ground_truth.json           # Eval ground-truth answers
│   └── sample_sales.csv            # Sample dataset for demos
│
├── workspace/
│   └── db.duckdb                   # Persistent DuckDB database file
│
├── .env                            # API keys and mode configuration
├── .env.example                    # Template for .env
├── requirements.txt
├── pytest.ini
├── README.md
├── SPEC.md
└── STATE.md
```

---

## 3. UI Architecture — Multipage Streamlit App

The application uses Streamlit's native **multipage routing** (`pages/` directory). Each page file calls the same `render_sidebar()` and `page_header()` helpers from `utils/shared.py`, ensuring a consistent look across all views.

### Page Map

| File | Route | Purpose |
|---|---|---|
| `app.py` | `/` (Home) | Landing page — hero section, nav cards, how-it-works steps, quick-ask input |
| `pages/2_BI_Analyst_Chat.py` | `/BI_Analyst_Chat` | Chat interface + right-panel live mini dashboard |
| `pages/3_Data_Cleaning_Profiling.py` | `/Data_Cleaning_Profiling` | 4-tab profiling view (Overview, Column Profiles, Data Quality, Log) |
| `pages/4_BI_Analytics_Dashboard.py` | `/BI_Analytics_Dashboard` | Full KPI dashboard — 4 metrics + 6 charts in a 2-column grid |
| `pages/5_SQL_Data_Explorer.py` | `/SQL_Data_Explorer` | Split-panel SQL console with auto-visualize |
| `pages/6_Settings.py` | `/Settings` | LLM config, app toggles, system info, dataset management |

### Sidebar (shared across all pages)

Rendered by `render_sidebar()` in `utils/shared.py`. Contains:

- **Brand header** — logo icon + app title
- **Current Dataset card** — active table name, row/column count, green/grey status dot
- **Dataset switcher** — `st.selectbox` shown when >1 table is loaded
- **File uploader** — accepts CSV, TSV, XLSX, Parquet, JSON, ZIP
- **Run Phase 1 (ETL) on Uploaded Data** button — triggers ingestion + profiling; label is test-critical and must not change
- **Format pills** — CSV / TSV / XLSX / Parquet / JSON / ZIP
- **Settings expander** — Gemini API key input + model selector
- **Status chip** — shows Gemini Mode (green) or Schema Planner (blue)

### Page Header (shared across all pages)

Rendered by `page_header(icon, title, subtitle)` in `utils/shared.py`. Displays:

- Icon box + title + subtitle on the left
- Active dataset pill + mode pill on the right
- Separated from main content by a bottom border

### BI Analyst Chat (`pages/2_BI_Analyst_Chat.py`)

Two-column layout: chat panel (left) + live mini-dashboard (right).

**Left — Chat:**
- Suggested Questions expander with 2-column button grid; questions are schema-aware when a dataset is loaded (reference actual column names)
- Scrollable chat history container (`height=480`)
- User messages rendered as right-aligned blue bubbles (`.user-msg-bubble`)
- Assistant responses as white cards with summary, root cause, impact, recommendation, embedded Plotly chart, and an evidence verification badge
- `st.chat_input` at the bottom; pending questions forwarded from Home page via `st.session_state["pending_question"]`
- Clear conversation button

**Right — Live Mini Dashboard:**
- 4 KPI metrics (primary measure total, secondary measure total, row count, average)
- Sales & Profit Trend chart
- Top 5 items table (live from DuckDB, with share %)
- Key Findings summary list

### Data Cleaning & Profiling (`pages/3_Data_Cleaning_Profiling.py`)

Four tabs:

| Tab | Content |
|---|---|
| **Overview** | 4 KPI metrics + Dataset Info table + Role Distribution pie chart + 100-row table preview |
| **Column Profiles** | Filterable column table (name, type, role, null %, distinct count, sample values) |
| **Data Quality** | Avg null %, null bar chart (top 20 cols), column quality table with 🟢/🟡/🔴 indicators |
| **Log** | Raw cleaning/audit log JSON from Phase 1 ETL |

### BI Analytics Dashboard (`pages/4_BI_Analytics_Dashboard.py`)

Full-width 2-column grid:

| Position | Chart |
|---|---|
| Row 1 left | Sales & Profit Trend (line chart, live aggregation by date column) |
| Row 1 right | Revenue by Category (bar chart, top 8 dimension values) |
| Row 2 left | Top Items horizontal bar (top N dimension values by measure, with % share) |
| Row 2 right | Outlier Detection (bar chart of outlier counts per metric column, z-score >2.5σ; falls back to radar placeholder) |
| Row 3 left | Forecast (linear extrapolation, 3 forward periods, with confidence interval shading) |
| Row 3 right | Quick Insights (live bullet list of dataset stats + amber recommendation) |

All charts are **live-first**: they query DuckDB for actual data and fall back to a labeled placeholder when no dataset is loaded.

### SQL & Data Explorer (`pages/5_SQL_Data_Explorer.py`)

Split-panel layout: query builder (left) + results (right).

**Left:**
- Pre-built preset dropdown (dynamically built from active schema — includes preview, count, measure summary, aggregate by dimension, monthly trend, distinct values, null check)
- SQL text editor (editable, pre-filled from preset)
- Execute / Clear buttons
- Schema Reference expander (column name, type, role, null %)

**Right:**
- Success banner with row/column count
- `st.dataframe` result table
- CSV download button
- Auto-Visualize expander: x/y axis selectors + Bar/Line/Scatter toggle → live Plotly chart

### Settings (`pages/6_Settings.py`)

Two-column layout:

**Left — Configuration:**
- Gemini API key text input (password-masked)
- Model selector (gemini-2.5-flash / gemini-2.5-pro / gemini-1.5-flash)
- API key status indicator (green = active, info = offline)
- Max Agent Steps slider (3–20)
- Data Cleaning and SQL Guard toggles
- Save Settings button (persists to `st.session_state.settings`)

**Right — System Info:**
- Version table: Python, Streamlit, DuckDB, Google GenAI, platform
- Loaded Datasets list with row count and active/loaded badge
- Clear All Datasets button
- Chat history message count + Clear Chat History button

---

## 4. Shared Module (`utils/shared.py`)

All cross-page logic lives here. Pages import only what they need.

### Exports

| Symbol | Type | Purpose |
|---|---|---|
| `GLOBAL_CSS` | `str` | Complete CSS injected via `st.markdown(..., unsafe_allow_html=True)` on every page |
| `init_session()` | function | Bootstraps all `st.session_state` keys with defaults; auto-selects first clean table |
| `render_sidebar()` | function | Renders the full dark sidebar on every page |
| `page_header(icon, title, subtitle)` | function | Renders the top header bar with dataset + mode pills |
| `get_active_meta()` | function | Returns `(active_tbl, catalog, roles, measures, dates, dimensions, row_count)` |
| `get_llm()` | function | Returns `(LLMClient, has_live_llm: bool)` |
| `compute_metrics(db, table)` | function | Queries DuckDB for KPI values; returns dict with totals, avg, labels |
| `chart_trend(...)` | function | Sales/measure trend line chart (live DuckDB or placeholder) |
| `chart_category(...)` | function | Bar chart of top dimension values by measure |
| `chart_top_items(...)` | function | Horizontal bar chart of top N items with % share |
| `chart_outliers(...)` | function | Outlier count bar chart per measure column (z-score >2.5σ) |
| `chart_forecast(...)` | function | Linear extrapolation forecast with CI shading |

### CSS Architecture

The `GLOBAL_CSS` string defines:

- Inter font loaded from Google Fonts
- App background (`#f8fafc`), full-width block container
- Dark navy sidebar (`#0b1120`) with hidden default Streamlit nav
- Sidebar button, file uploader, and selectbox styling
- Page header (`top-header-bar`) layout
- Process flow stepper cards (`.step-card`, `.step-badge`, `.step-connector`)
- KPI cards (`.kpi-card`, `.kpi-value`, `.kpi-delta`)
- Chat bubbles (`.user-msg-bubble`, `.assistant-response-container`)
- Evidence card (`.evidence-card`), recommendation box (`.rec-box-amber`)
- Format pills (`.format-pill`)
- **Expander arrow fix** — see [Section 12](#12-known-css-fix--expander-arrow-overlap)

---

## 5. Universal Ingestion Pipeline (`core/ingest.py`)

Accepts single tabular files or ZIP archives containing multiple tabular files.

### Capabilities

- **Formats:** `.csv`, `.tsv`, `.xlsx`, `.parquet`, `.json`, `.zip`
- **Zip-Slip Defense:** Sanitizes all archive paths using `os.path.abspath` and `os.path.commonpath` to block directory traversal attacks
- **Table Naming:** Filenames slugged to safe SQL identifiers: `ds_<clean_slug>`. Collisions disambiguated with numeric suffixes (`ds_sales_2`)
- **Ingestion Manifest:** Returns `{"accepted": [...], "skipped": [...]}` with per-file row counts, table names, and source filenames

---

## 6. Data Profiling, Cleaning & Cataloging

Managed by `core/profiler.py`, orchestrated by `phases/phase1_etl.py`.

### Automated Pipeline

1. **Role Inference** (deterministic, no LLM):
   - `id` — matches ID naming patterns or 100% unique non-float values
   - `date` — ISO-formatted or parseable temporal strings
   - `measure` — continuous numeric columns (FLOAT, DOUBLE, BIGINT, DECIMAL, INTEGER)
   - `dimension` — discrete categoricals with low cardinality or repeating values
   - `text` — long unstructured string fields

2. **Sanitization:**
   - Trims whitespace on all text columns
   - Normalizes sentinel nulls: `"NULL"`, `"N/A"`, `""`, `"none"`, `"-"` → SQL `NULL`

3. **Deduplication:**
   - Pass 1: exact whole-row deduplication
   - Pass 2: high-confidence primary key dedup (ID column + temporal tie-breaking)

4. **Clean Catalog:**
   - Raw tables (`ds_<slug>`) → cleaned tables (`clean_<slug>`)
   - Metadata persisted in `workspace/catalog.json`
   - Returned as a Python dict (stored in `st.session_state.catalogs[table_name]`)

---

## 7. Security & AST SQL Guard (`core/sql_guard.py`)

All user-supplied and agent-generated SQL is parsed by SQLGlot with the DuckDB dialect.

### Rules

| Rule | Detail |
|---|---|
| Statement type | Only pure `SELECT` — no `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA` |
| Function blocking | Blocks `read_csv`, `read_parquet`, `read_json`, `glob`, `scan`, `external_query` by AST node type — substring matching avoided to prevent false positives on column names like `load_timestamp` |
| Table validation | Table names cross-referenced against the active schema whitelist |
| CTE awareness | `WITH ranked AS (...)` definitions recognised; downstream references accepted |
| Alias resolution | `SELECT`-expression aliases permitted in `GROUP BY`, `ORDER BY`, `HAVING` |
| Row limit | Auto-injects `LIMIT 1000` if no smaller limit is specified |

---

## 8. Core Agentic Loop & Prompt Grounding

Orchestrated by `core/agent_loop.py` (`RunController`) and `phases/phase2_analysis.py`.

### Workflow

1. **Dynamic Prompt Grounding** — `format_catalog_for_prompt()` builds the system prompt on-the-fly with column names, inferred roles, sample values, and JSON tool argument schemas.
2. **Disambiguation (`AskUser`)** — when multiple tables are loaded and intent is ambiguous, the agent yields `AskUser` instead of guessing.
3. **Budget Enforcement** — `RunController` caps total steps (default 8), cumulative API tokens, and consecutive error count.
4. **Verification** — `FinalAnswer` numerical claims are checked by `core/verifier.py`. If claims fail, one repair round is granted with explicit feedback before finalization.
5. **Trace Logging** — every run produces a JSONL file under `data/traces/`.
6. **HITL Pause/Resume** — long-running analyses can be paused mid-execution and resumed from `data/state/`.

---

## 9. Analytical Tools (`tools/`)

All tools are wrapped with Pydantic v2 schemas, thread-level timeout guards (`execute_with_timeout`), and safe SQL identifier quoting.

### `compute_kpi`
Aggregated metric computation.

| Argument | Type | Description |
|---|---|---|
| `table` | str | Target table name |
| `kpi` | str | Metric column name |
| `aggregation` | str | `sum` / `avg` / `count` / `min` / `max` (default: `sum`) |
| `filters` | optional | `[{"column": …, "op": "=", "value": …}]` or SQL string |

Returns: `{table, kpi, aggregation, value, row_count}`

### `trend_analysis`
Period-over-period comparison.

| Argument | Type | Description |
|---|---|---|
| `table` | str | Target table |
| `metric` | str | Numeric column |
| `date_column` | str | Date/time column |
| `aggregation` | str | Default: `sum` |
| `grain` | str | `day` / `week` / `month` / `quarter` / `year` (default: `month`) |
| `filters` | optional | Filter conditions |

Returns: `{last_period, prior_period, diff, percent_change, grain, aggregation}`

### `drilldown_by_dimension`
Multi-dimensional ranking and breakdown.

| Argument | Type | Description |
|---|---|---|
| `table` | str | Target table |
| `metric` | str | Numeric column |
| `date_column` | str | Date column |
| `dimensions` | list[str] | Categorical columns to break down |
| `aggregation` | str | Default: `sum` |
| `filters` | optional | Filter conditions |

Returns: `{changes: [{dimension_values, last_period, prior_period, diff, percent_change}]}`

### `detect_anomalies`
Statistical outlier detection.

| Argument | Type | Description |
|---|---|---|
| `table` | str | Target table |
| `metric` | str | Numeric column |
| `date_column` | str | Date column |
| `method` | str | `zscore` (3σ) or `iqr` (1.5 IQR) — default: `zscore` |
| `aggregation` | str | Default: `sum` |
| `grain` | str | Temporal grain — default: `day` |
| `filters` | optional | Filter conditions |

Returns: `{anomalies: [dates], count, method, grain}`

### `forecast`
Forward projection with confidence intervals.

| Argument | Type | Description |
|---|---|---|
| `table` | str | Target table |
| `metric` | str | Numeric column |
| `date_column` | str | Date column |
| `horizon` | int | Periods to project (default: 7) |
| `grain` | str | Temporal grain — default: `day` |
| `aggregation` | str | Default: `sum` |
| `filters` | optional | Filter conditions |

Returns: `{forecast: [values], intervals: [{lower, upper}]}`

### `make_chart`
Plotly chart creation and serialization.

| Argument | Type | Description |
|---|---|---|
| `chart_type` | str | `bar` / `line` / `scatter` |
| `data` | list[dict] | Row records |
| `x_col` | str | X-axis field |
| `y_col` | str | Y-axis field |
| `title` | str | Chart title |

Returns: `{chart_id: uuid, status: "saved"}` — file written to `data/charts/<uuid>.json`

### `run_sql`
AST-guarded raw SQL executor.

| Argument | Type | Description |
|---|---|---|
| `query` | str | Valid analytical SELECT query |

Returns: list of result row dicts, or error payload on validation/execution failure.

---

## 10. Anti-Hallucination Verifier (`core/verifier.py`)

Prevents AI hallucination by validating all numeric claims against query evidence before the response reaches the user.

### Extraction & Noise Filters

Numbers are extracted from claim strings then filtered to remove:
- Calendar years (1900–2099)
- Formatted dates (`YYYY-MM-DD`, `MM/DD/YYYY`)
- Alphanumeric codes and entity IDs (`E1`, `EMP102`, `ord_994`)
- Comma-formatted values are normalized first (`$120,000` → `120000`)

### Verification Scope

- Every entry in `findings` is checked against its cited `evidence_ids`
- Top-level narrative fields (`summary`, `quantified_impact`, `root_cause`, `recommendation`) are checked against all cited evidence

### Allowed Derivations

A number passes verification if it matches any of:

| Derivation | Formula |
|---|---|
| Exact match | `abs(claim - evidence) / max(abs(evidence), 1) < tolerance` |
| Difference | `abs(e1 - e2)` |
| Sum | `e1 + e2` |
| Ratio | `e1 / e2` or `e2 / e1` |
| Percentage change | `((e1 - e2) / e2) × 100` |

---

## 11. Zero-Cost Offline Planner (`phases/planner.py`)

When no Gemini API key is configured, the application runs entirely offline using the schema-driven planner:

- Infers column roles directly from the DuckDB schema
- Routes questions to appropriate tools based on keyword detection in the user query
- Runs `compute_kpi`, `trend_analysis`, `detect_anomalies`, `drilldown_by_dimension` as needed
- Records all outputs into the `EvidenceLedger` and verifies structured findings
- Generates interactive Plotly figures and returns them alongside the structured answer dict

No network calls, no API tokens, no cost.

---

## 12. Known CSS Fix — Expander Arrow Overlap

**Symptom:** The text `_arrow_right` (or similar glyph name) appears overlaid on top of expander labels, making them unreadable.

**Root cause:** The global CSS rule `*, *::before, *::after { font-family: … !important }` overrides Streamlit's internal `::before` pseudo-element that renders the collapse arrow as a font glyph. When overridden, the browser falls back to rendering the glyph's raw name as visible text, and it stacks directly on the label because the `<summary>` element loses its flex layout.

**Fix applied in `utils/shared.py` (`GLOBAL_CSS`):**

```css
/* Only * gets the font override — NOT ::before / ::after */
* {
    font-family: 'Inter', … !important;
}

/* Suppress native browser details triangle */
details > summary { list-style: none !important; }
details > summary::-webkit-details-marker { display: none !important; }

/* Restore Streamlit expander layout */
[data-testid="stExpander"] details summary {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}
[data-testid="stExpander"] details summary svg {
    flex-shrink: 0 !important;
    order: -1 !important;   /* arrow left of label */
}
[data-testid="stExpander"] details summary p,
[data-testid="stExpander"] details summary span {
    margin: 0 !important;
    order: 1 !important;
}
```

This pattern must be preserved whenever the global font override is modified.

---

## 13. Testing & Quality Assurance

The test suite runs **90 tests, 100% offline**, with zero real network or LLM calls.

```bash
pytest -q          # full suite
pytest tests/test_ui.py -v    # UI smoke tests only
```

### Test Modules

| File | Coverage |
|---|---|
| `test_ui.py` | Multipage smoke tests — each of the 6 pages renders without exception via `AppTest.from_file()`; sidebar ETL button label verified; navigation radio options verified; empty-state info messages verified |
| `test_analytics_tools.py` | All 7 analytical tools (`compute_kpi`, `trend_analysis`, `detect_anomalies`, `drilldown_by_dimension`, `forecast`, `make_chart`, `run_sql`) + invalid argument handling |
| `test_core_advanced.py` | `EvidenceLedger`, loop guards, verifier pass/fail, agent loop happy path, budget enforcement, HITL pause/resume, disallowed tool rejection, integration flow |
| `test_core_harness.py` | SQL guard (allowed SELECT, blocked DML, multi-statement, file functions, comment injection, limit injection), tool registry (disallowed, invalid args, raising, timeout, compaction, schema), LLM mock ordering, parse repair, record/replay, backoff, DuckDB CSV load, immutable raw table, schema introspection |
| `test_data_generator.py` | Synthetic data generation and deterministic reproducibility |
| `test_eval_runner.py` | Benchmark evaluator dry-run |
| `test_generic_cleaning.py` | Role inference, deduplication, sentinel null normalization across Sales, HR, and Web Events fixtures |
| `test_generic_tools.py` | All analytics tools tested across two distinct schemas (Employees / HR and IoT Sensors) + invalid identifier rejection |
| `test_ingest.py` | Multi-dataset coexistence, empty file handling, ZIP with mixed formats and Zip-Slip defense |
| `test_offline_planner.py` | End-to-end zero-cost planner for general overview, trend, anomaly, breakdown, and missing-table queries |
| `test_phase1.py` | Phase 1 success path and LLM retry logic |
| `test_phase2.py` | Phase 2 success path and verify-then-repair flow |
| `test_phase2_grounding.py` | Schema catalog in prompt, silent-fallback prevention, `AskUser` disambiguation |
| `test_sql_guard_ast.py` | `load_timestamp` column false-positive, `SELECT` aliases in `GROUP BY`/`ORDER BY`, CTEs, unknown table, unknown column suggestion, `read_csv` / `read_parquet` / `read_json` blocking, `DROP` blocking, multi-statement blocking |
| `test_verifier_comprehensive.py` | Number extraction filtering, derivation math (difference, ratio, percent change), happy-path verification, fabricated findings rejection, fabricated narrative rejection, missing evidence ID, date/ID exclusion |

### UI Test Details (`test_ui.py`)

Each page is tested with `AppTest.from_file(path, default_timeout=60)`:

```
test_home_page_renders           → app.py
test_chat_page_renders           → pages/2_BI_Analyst_Chat.py
test_data_cleaning_page_renders  → pages/3_Data_Cleaning_Profiling.py
test_dashboard_page_renders      → pages/4_BI_Analytics_Dashboard.py
test_sql_explorer_page_renders   → pages/5_SQL_Data_Explorer.py
test_settings_page_renders       → pages/6_Settings.py
```

The ETL button label `"Run Phase 1 (ETL) on Uploaded Data"` is asserted on every sidebar test. **Do not rename this button** — it is a cross-test contract.
