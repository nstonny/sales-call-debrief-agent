# Sales Call Debrief Agent

LLM-powered pipeline for analyzing sales call transcripts and returning structured coaching insights with RAG-backed context.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C)](https://qdrant.tech/)
[![Langfuse](https://img.shields.io/badge/Langfuse-Observability-0EA5E9)](https://langfuse.com/)

## What This Project Does

- Accepts a `.txt` sales transcript via `POST /api/upload`
- Extracts metadata (`rep_name`, `contact_name`, `contact_title`, `deal_stage`)
- Runs a retrieval-backed debrief agent with LangChain tool calling
- Returns and persists structured `AnalysisResult` fields:
  - `summary`, `next_steps`, `competitor_mentioned`
  - `strengths`, `areas_for_improvement`, `action_items`, `objections_raised`
  - `sentiment`, `score`

## Current Architecture

1. **Upload route**: `src/debrief_agent/api/routes/upload.py`
2. **Extraction service**: `src/debrief_agent/rag/agent/services/extraction.py`
3. **Analysis service**: `src/debrief_agent/rag/agent/sales_debrief_agent.py`
4. **RAG tools**: `src/debrief_agent/rag/agent/tools.py`
5. **Retriever**: `src/debrief_agent/rag/retrieval/hybrid_retriever.py`
6. **Persistence**: async SQLAlchemy models in `src/debrief_agent/models/`


## Prerequisites

- Python 3.13+
- PostgreSQL
- Qdrant (local or remote)
- OpenAI API key
- `uv`

Install `uv` if needed:

```zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

```zsh
git clone https://github.com/nstonny/sales-call-debrief-agent.git
cd sales-call-debrief-agent
uv venv
source .venv/bin/activate
uv sync
```

Create `.env` in repo root:

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
OPENAI_API_KEY=sk-...

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=sales_knowledge_chunks
QDRANT_TIMEOUT_SECONDS=10

# Optional
DEBRIEF_AGENT_MODEL=gpt-5-mini
DEBRIEF_AGENT_LOG_RAG_CHUNKS=false
```

Run migrations:

```zsh
uv run alembic upgrade head
```

## Run the App

Backend API:

```zsh
uv run uvicorn debrief_agent.app.main:app --reload
```

Streamlit UI (second terminal):

```zsh
uv run streamlit run src/ui/streamlit_app.py
```

Endpoints:

- API docs: `http://localhost:8000/docs`
- UI: `http://localhost:8501`

## API Usage

### Upload and analyze transcript

```zsh
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@src/data/transcripts/transcript_1.txt" \
  -F "company=Acme GmbH" \
  -F "deal_value=25000"
```

### Expected behavior

- Validates `.txt` + UTF-8
- Persists `Call`
- Runs extraction + analysis
- Persists `Analysis`
- Returns full `CallResponse` with nested `analysis`

## Service Usage (Internal)

```python
from debrief_agent.rag.agent.services.extraction import MetadataExtractor
from debrief_agent.rag.agent import SalesDebriefAgent

metadata_extractor = MetadataExtractor()
analyzer = SalesDebriefAgent()

transcript = "..."
metadata = await metadata_extractor.extract(transcript)
analysis = await analyzer.analyze(transcript=transcript, metadata=metadata)
```

## RAG Ingestion Commands

These CLIs import `debrief_agent.app.bootstrap_qdrant.ensure_collection`.
If `src/debrief_agent/app/bootstrap_qdrant.py` is missing in your checkout,
the ingestion modules will fail to import.

### 1) Sales frameworks markdown ingestion

Module: `src/debrief_agent/rag/ingestion/ingest_pdf_documents.py`

Dry-run:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_pdf_documents --dry-run
```

Ingest into Qdrant:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_pdf_documents
```

### 2) Coaching guides ingestion

Module: `src/debrief_agent/rag/ingestion/ingest_coaching_guides.py`

Dry-run:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_coaching_guides --dry-run
```

Ingest into Qdrant:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_coaching_guides
```

### 3) Call examples ingestion

Module: `src/debrief_agent/rag/ingestion/ingest_call_examples.py`

Dry-run:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_call_examples --dry-run
```

Ingest into Qdrant:

```zsh
uv run python -m debrief_agent.rag.ingestion.ingest_call_examples
```

### 4) Convert PDF to markdown (MarkItDown)

Module: `src/debrief_agent/rag/scripts/document_processing/convert_pdf_to_markdown_markitdown.py`

```zsh
uv run python -m debrief_agent.rag.scripts.document_processing.convert_pdf_to_markdown_markitdown
```

## Debugging and Observability

### RAG chunk logging

To inspect retrieved chunks in the API terminal:

```zsh
export DEBRIEF_AGENT_LOG_RAG_CHUNKS=true
uv run uvicorn debrief_agent.app.main:app --reload
```

When tools are called, logs include:

- retrieval type and query
- number of returned chunks
- per chunk: score, source, preview text

### Langfuse tracing

Spans include fields like:

- `service`
- `model`
- `trace_id`
- `session_id`
- `error_type`
- `validation_ok`

## Project Structure

```text
sales-call-debrief-agent/
├── migrations/
├── src/
│   ├── data/
│   │   ├── knowledge_base/
│   │   ├── transcripts/
│   │   └── ...
│   ├── debrief_agent/
│   │   ├── api/
│   │   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── rag/
│   │   │   ├── agent/
│   │   │   │   ├── prompts/
│   │   │   │   ├── services/
│   │   │   │   ├── sales_debrief_agent.py
│   │   │   │   └── tools.py
│   │   │   ├── ingestion/
│   │   │   ├── retrieval/
│   │   │   ├── scripts/
│   │   │   └── vectorstore/
│   │   └── schemas/
│   └── ui/
├── experiments.local/
├── pyproject.toml
└── README.md
```

## Troubleshooting

- **`OPENAI_API_KEY is not set`**
  - Set it in `.env` and restart the API process.
- **`DATABASE_URL is not set`**
  - Set it in `.env`, then run migrations.
- **`POST /api/upload` returns 502**
  - Check API logs for extraction or analysis validation errors.
  - If tools are expected but not used, verify prompts under `rag/agent/prompts/analysis.py`.
- **No RAG chunk logs visible**
  - Ensure `DEBRIEF_AGENT_LOG_RAG_CHUNKS=true` in the same process running Uvicorn.
  - Ensure tools are actually called for that request.
- **Ingestion CLI import fails with `No module named debrief_agent.app.bootstrap_qdrant`**
  - Add/restore `src/debrief_agent/app/bootstrap_qdrant.py`, then rerun ingestion.
- **`uv: command not found`**
  - Install `uv`, restart shell, verify with `uv --version`.
