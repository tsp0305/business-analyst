# Agentic BI Business Analyst

A framework-free, universal Agentic BI Business Analyst system with a multipage Streamlit UI. Translates business questions into multi-step analytical tool calls, executes them against DuckDB, verifies every number to prevent hallucinations, and renders interactive Plotly visualizations across **any tabular dataset** or **ZIP archive**.

---

## Key Features

- **Universal Tabular Ingestion** — CSV, TSV, XLSX, Parquet, JSON, ZIP with Zip-Slip protection and automatic slug-based table naming.
- **Dynamic Schema Profiling & Cleaning** — automatic role inference (`measure`, `date`, `dimension`, `id`, `text`), whitespace trimming, sentinel null normalization, exact + key-level deduplication.
- **No Heavy Frameworks** — pure Python 3.11+, DuckDB, Pandas, Plotly. No LangChain, LlamaIndex, or CrewAI.
- **AST SQL Security** — SQLGlot parses all queries into abstract syntax trees; blocks DDL/DML and file-loading functions without false positives on valid column names.
- **Agent Harness (`RunController`)** — step budget, token budget, consecutive error recovery, JSONL trace logging, and human-in-the-loop (HITL) pause/resume.
- **Anti-Hallucination Verifier** — every number in `summary`, `quantified_impact`, `root_cause`, `recommendation`, and `findings` is cross-checked against the `EvidenceLedger` before reaching the user.
- **Dual Execution Engine:**
  - **Gemini AI Mode** — live Google GenAI with schema-grounded prompts and multi-dataset disambiguation.
  - **Zero-Cost Schema Planner** — fully offline, deterministic, no API key required.
- **Multipage Streamlit UI** — 6 dedicated pages with a shared dark sidebar, consistent header bar, and live-data charts.

---

## Pages

| Page | Path | Description |
|---|---|---|
| Home | `app.py` | Landing page — hero, quick-ask input, nav cards, how-it-works |
| BI Analyst Chat | `pages/2_BI_Analyst_Chat.py` | Conversational chat + right-panel live mini dashboard |
| Data Cleaning & Profiling | `pages/3_Data_Cleaning_Profiling.py` | 4-tab profiling (overview, columns, quality, log) |
| BI Analytics Dashboard | `pages/4_BI_Analytics_Dashboard.py` | 4 KPI cards + 6 live charts in a 2-column grid |
| SQL & Data Explorer | `pages/5_SQL_Data_Explorer.py` | DuckDB SQL console + auto-visualize |
| Settings | `pages/6_Settings.py` | API key, model, toggles, system info, dataset management |

---

## Project Structure

```
BI-analyst/
├── app.py                          # Entry point (Home page)
├── pages/                          # Streamlit multipage files
│   ├── 2_BI_Analyst_Chat.py
│   ├── 3_Data_Cleaning_Profiling.py
│   ├── 4_BI_Analytics_Dashboard.py
│   ├── 5_SQL_Data_Explorer.py
│   └── 6_Settings.py
├── utils/
│   └── shared.py                   # CSS, session state, sidebar, chart helpers
├── core/                           # Agent framework
│   ├── agent_loop.py               # RunController
│   ├── context.py                  # Prompt grounding
│   ├── db.py                       # DuckDB wrapper
│   ├── evidence.py                 # EvidenceLedger
│   ├── guards.py                   # Anti-oscillation guards
│   ├── hitl.py                     # HITL pause/resume
│   ├── ingest.py                   # Ingestion engine
│   ├── llm.py                      # LLMClient + Gemini provider
│   ├── memory.py                   # Thread memory
│   ├── profiler.py                 # Column profiler & catalog
│   ├── schemas.py                  # Pydantic action schemas
│   ├── sql_guard.py                # AST SQL validator
│   ├── tools.py                    # Tool registry
│   ├── trace.py                    # JSONL tracer
│   └── verifier.py                 # Number verifier
├── phases/
│   ├── phase1_etl.py               # ETL orchestration
│   ├── phase2_analysis.py          # Agentic analysis
│   └── planner.py                  # Offline schema planner
├── tools/                          # Analytical tool modules
│   ├── base_tool.py
│   ├── anomaly_tool.py
│   ├── chart_tool.py
│   ├── drilldown_tool.py
│   ├── forecast_tool.py
│   ├── kpi_tool.py
│   ├── python_tool.py
│   ├── sql_tool.py
│   └── trend_tool.py
├── evals/
│   ├── generate_data.py
│   └── run_eval.py
├── tests/                          # 90 tests, 100% offline
├── data/                           # Charts, traces, state, uploads, sample data
├── workspace/db.duckdb             # Persistent DuckDB file
├── .env                            # API keys
├── requirements.txt
└── pytest.ini
```

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```env
# .env
GEMINI_API_KEY=your_key_here   # optional — omit to run fully offline
```

> Without an API key the app runs in **Zero-Cost Schema Planner Mode** — all chat, charts, and dashboards work locally with zero network calls.

### 3. Run the app

```bash
streamlit run app.py
```

Open `http://localhost:8501`.

### 4. Run the test suite

```bash
pytest -q
```

90 tests, all offline, ~2 minutes.

---

## Analytical Tools

| Tool | Key Arguments | Returns |
|---|---|---|
| `compute_kpi` | `table`, `kpi`, `aggregation` (sum/avg/count/min/max), `filters` | Aggregated metric value + row count |
| `trend_analysis` | `table`, `metric`, `date_column`, `grain` (day/week/month/quarter/year) | Last period, prior period, diff, % change |
| `drilldown_by_dimension` | `table`, `metric`, `date_column`, `dimensions` | Per-dimension period-over-period changes |
| `detect_anomalies` | `table`, `metric`, `date_column`, `method` (zscore/iqr), `grain` | Anomalous dates + count |
| `forecast` | `table`, `metric`, `date_column`, `horizon`, `grain` | Projected values + confidence intervals |
| `make_chart` | `chart_type` (bar/line/scatter), `data`, `x_col`, `y_col`, `title` | Chart UUID written to `data/charts/` |
| `run_sql` | `query` | Query result rows (AST-validated, read-only) |

---

## Tech Stack

| Component | Library |
|---|---|
| Web UI | Streamlit |
| Analytical database | DuckDB |
| Data manipulation | Pandas |
| Visualizations | Plotly Express + Graph Objects |
| AI provider | Google GenAI SDK (`google-genai`) |
| SQL validation | SQLGlot |
| Data schemas | Pydantic v2 |
| Time-series | statsmodels |
| File formats | openpyxl (XLSX), PyYAML |
| Resilience | tenacity (exponential backoff) |
| Testing | Pytest |
