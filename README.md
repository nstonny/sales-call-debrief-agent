# Sales Call Debrief Agent

LLM-powered pipeline for analyzing sales call transcripts and producing structured coaching insights and CRM-ready outputs.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-Async-CC2927?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-4B5563)](https://alembic.sqlalchemy.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Responses_API-412991?logo=openai&logoColor=white)](https://platform.openai.com/docs/api-reference/responses)
[![Langfuse](https://img.shields.io/badge/Langfuse-Observability-0EA5E9)](https://langfuse.com/)
[![uv](https://img.shields.io/badge/uv-Package_Manager-111827)](https://docs.astral.sh/uv/)

This project includes:
- a FastAPI backend (`/api/upload`) for transcript ingestion and analysis,
- async SQLAlchemy + PostgreSQL persistence,
- Alembic migrations,
- a Streamlit UI for upload and dashboarding,
- and a CLI runner to compare rubric-driven analysis experiments.

## Table of Contents

- [Tech Stack](#tech-stack)
- [Features](#features)
- [LLM Models Used](#llm-models-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quickstart (First Run)](#quickstart-first-run)
- [Usage](#usage)
- [Experiments CLI (Rubric Testing)](#experiments-cli-rubric-testing)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Tech Stack

- Python 3.13+
- FastAPI
- Streamlit
- SQLAlchemy (async) + asyncpg
- PostgreSQL
- Alembic
- OpenAI Responses API
- Langfuse (observability/tracing)
- uv
- Jupyter (dev dependency)

## Features

- Upload `.txt` sales call transcripts from the UI.
- Extract metadata with LLMs:
  - `rep_name`
  - `contact_name`
  - `contact_title`
  - `deal_stage`
- Generate structured analysis/debrief with:
  - `summary`, `strengths`, `areas_for_improvement`, `action_items`
  - `objections_raised`, `competitor_mentioned`, `next_steps`
  - `sentiment`, `score`
  - parsed via OpenAI Responses structured parsing into `AnalysisResult`
- Persist calls + analyses in PostgreSQL.
- Run rubric-driven experiment batches via CLI and write results to JSONL.
- Use backend-controlled default rubrics (`ANALYSIS_RUBRICS`) without exposing rubric choice in the UI.

## LLM Models Used

From current service code:
- Extraction: `gpt-4.1-mini` (`src/debrief_agent/services/extraction.py`)
- Analysis: `gpt-5-mini` (`src/debrief_agent/services/analysis.py`)

## Prerequisites

- Python 3.13+
- PostgreSQL running locally (or reachable remote instance)
- OpenAI API key
- `uv` installed

Install `uv` if needed:

```zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

### 1) Clone and enter project

```zsh
git clone https://github.com/nstonny/sales-call-debrief-agent.git
cd sales-call-debrief-agent
```

### 2) Create and activate virtual environment

```zsh
uv venv
source .venv/bin/activate
```

### 3) Install dependencies

```zsh
uv sync
```

### 4) Configure environment variables

Create `.env` in project root:

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
OPENAI_API_KEY=sk-...
# Optional override of backend defaults
ANALYSIS_RUBRICS=overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt
```

### 5) Run migrations

```zsh
uv run alembic upgrade head
```

## Quickstart (First Run)

Copy/paste this from project root:

```zsh
uv venv
source .venv/bin/activate
uv sync
uv run alembic upgrade head
uv run uvicorn debrief_agent.app.main:app --reload
```

In a second terminal:

```zsh
source .venv/bin/activate
streamlit run src/ui/streamlit_app.py
```

Then open:
- API docs: `http://localhost:8000/docs`
- UI: `http://localhost:8501`

## Usage

### Run backend API

```zsh
uv run uvicorn debrief_agent.app.main:app --reload
```

### Run Streamlit frontend

```zsh
streamlit run src/ui/streamlit_app.py
```

### Upload + analyze via API (example)

```zsh
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@src/data/transcripts/transcript_1.txt" \
  -F "company=Acme GmbH" \
  -F "deal_value=25000"
```

### Service usage (internal)

Service APIs are class-based only:

```python
from debrief_agent.services.analysis import CallAnalyzer
from debrief_agent.services.extraction import MetadataExtractor

metadata_extractor = MetadataExtractor()
call_analyzer = CallAnalyzer()

metadata = await metadata_extractor.extract(transcript_text)
analysis = await call_analyzer.analyze(
    transcript=transcript_text,
    metadata=metadata,
    rubric_names=["overpitching_rubric.txt"],
)
```

Backward-compatibility function wrappers were removed from services; use
`MetadataExtractor.extract(...)` and `CallAnalyzer.analyze(...)` directly.

### Langfuse metadata taxonomy

When Langfuse tracing is enabled, the service spans include bounded metadata fields that can be used for filtering in the Langfuse UI.

Common fields:
- `service`: `extraction` or `analysis`
- `model`: `gpt-4.1-mini` (extraction) or `gpt-5-mini` (analysis)
- `trace_id`: current Langfuse trace identifier (when available)
- `session_id`: upload flow uses persisted `call.id` for cross-span correlation
- `had_refusal`: `true`/`false`
- `validation_ok`: `true`/`false`
- `error_type`: failure taxonomy value

`error_type` values by service:
- Extraction (`src/debrief_agent/services/extraction.py`):
  - `none`, `openai_error`, `llm_refusal`, `validation_error`
- Analysis (`src/debrief_agent/services/analysis.py`):
  - `none`, `rubric_error`, `openai_error`, `llm_refusal`, `validation_error`

`rubric_error` is analysis-only and indicates rubric file resolution failed before the LLM call.

## Experiments CLI (Rubric Testing)

CLI module: `src/debrief_agent/app/run_rubric_experiments.py`

It runs extraction + analysis for exactly one transcript per command and writes one JSON object to JSONL.

### Single bundled transcript + backend default rubrics

```zsh
uv run python -m debrief_agent.app.run_rubric_experiments \
  --transcript "src/data/transcripts/transcript_1.txt"
```

### Single bundled transcript + one rubric

```zsh
uv run python -m debrief_agent.app.run_rubric_experiments \
  --transcript "src/data/transcripts/transcript_6.txt" \
  --rubrics overpitching_rubric.txt \
  --out "experiments/transcript_6_overpitching.jsonl"
```

### Single bundled transcript + no rubrics

Use `--no-rubrics` to bypass rubric injection for that run.

```zsh
uv run python -m debrief_agent.app.run_rubric_experiments \
  --transcript "src/data/transcripts/transcript_6.txt" \
  --no-rubrics \
  --out "experiments/transcript_6_no_rubrics.jsonl"
```

### Single bundled transcript + all rubrics

```zsh
uv run python -m debrief_agent.app.run_rubric_experiments \
  --transcript "src/data/transcripts/transcript_6.txt" \
  --rubrics overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt \
  --out "experiments/transcript_6_all_rubrics.jsonl"
```

### Output and inspection

Default output: `experiments/rubric_runs.jsonl`

```zsh
cat experiments/rubric_runs.jsonl
```

Quick summary view:

```zsh
python - <<'PY'
import json
from pathlib import Path

for line in Path("experiments/rubric_runs.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    print(f"{row['transcript_name']} | rubrics={','.join(row['rubrics'])} | score={row['score']} | sentiment={row['sentiment']}")
PY
```

## Project Structure

```text
sales-call-debrief-agent/
├── migrations/                      # Alembic migrations
├── src/
│   ├── data/
│   │   ├── rubrics/                 # Rubric text files used for analysis prompt injection
│   │   └── transcripts/             # Bundled transcript fixtures (training/stress-test)
│   ├── debrief_agent/
│   │   ├── api/                     # FastAPI routers/routes
│   │   ├── app/                     # App entrypoints + CLI tools
│   │   ├── core/                    # Config + database setup
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── prompts/                 # Prompt templates + rubric loader utilities
│   │   ├── schemas/                 # Pydantic schemas
│   │   └── services/                # LLM extraction/analysis services
│   └── ui/
│       └── streamlit_app.py         # Streamlit dashboard
├── experiments/                     # JSONL experiment outputs
├── pyproject.toml
└── README.md
```

## Configuration

From `src/debrief_agent/core/config.py`:

- `DATABASE_URL` (required)
  - Example: `postgresql+asyncpg://user:pass@localhost:5432/debrief_db`
- `OPENAI_API_KEY` (required)
- `ANALYSIS_RUBRICS` (optional)
  - Comma-separated rubric filenames from `src/data/rubrics`
  - Default: `overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt`

## Troubleshooting

- **`OPENAI_API_KEY is not set`**
  - Add `OPENAI_API_KEY=...` to `.env`, then restart the API process.
- **`DATABASE_URL is not set`**
  - Add `DATABASE_URL=postgresql+asyncpg://...` to `.env` and rerun migrations.
- **Alembic upgrade fails**
  - Verify Postgres is running and reachable, then run:
    ```zsh
    uv run alembic upgrade head
    ```
- **Upload returns 422 for rubric file**
  - Check `ANALYSIS_RUBRICS` entries match filenames in `src/data/rubrics`.
- **Streamlit shows upload failure with no JSON body**
  - Inspect API logs in the `uvicorn` terminal for the root error.
- **`uv: command not found`**
  - Install uv:
    ```zsh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
  - Restart your shell and verify:
    ```zsh
    uv --version
    ```


