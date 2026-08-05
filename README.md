# Sales Call Debrief Agent

FastAPI + Streamlit app for analyzing sales call transcripts, returning structured coaching insights, and persisting the results with RAG-backed context.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C)](https://qdrant.tech/)
[![Langfuse](https://img.shields.io/badge/Langfuse-Observability-0EA5E9)](https://langfuse.com/)

## 30-Second Recruiter Snapshot

**Problem →** Sales teams lose valuable coaching insights because call reviews are manual, inconsistent, and slow.

**Method →** Built a FastAPI + Streamlit app that ingests sales transcripts, extracts deal metadata, and runs a RAG-backed AI debrief agent to generate structured coaching feedback.

**Result →** Produces immediate, repeatable call analysis (summary, strengths, objections, action items, sentiment, score) and stores results for ongoing coaching and performance tracking.

**How to run →** `uv sync` → `uv run alembic upgrade head` → start API: `uv run uvicorn debrief_agent.app.main:app --reload` → start UI: `uv run streamlit run src/ui/streamlit_app.py`.

## What This Project Does

- Accepts a UTF-8 `.txt` sales transcript via `POST /api/upload`
- Extracts metadata (`rep_name`, `contact_name`, `contact_title`, `deal_stage`) with OpenAI structured parsing
- Runs a retrieval-backed debrief agent with LangChain tool calling against Qdrant
- Persists `Call` and `Analysis` records, then returns structured `AnalysisResult` fields:
  - `summary`, `next_steps`, `competitor_mentioned`
  - `strengths`, `areas_for_improvement`, `action_items`, `objections_raised`
  - `sentiment`, `score`

## Current Architecture

1. **App entrypoint**: `src/debrief_agent/app/main.py`
2. **Upload route**: `src/debrief_agent/api/routes/upload.py`
3. **Extraction service**: `src/debrief_agent/rag/agent/services/extraction.py`
4. **Analysis service**: `src/debrief_agent/rag/agent/sales_debrief_agent.py`
5. **RAG tools**: `src/debrief_agent/rag/agent/tools.py`
6. **Retriever / vector store**: `src/debrief_agent/rag/retrieval/hybrid_retriever.py` and `src/debrief_agent/rag/vectorstore/qdrant_store.py`
7. **Observability**: `src/debrief_agent/core/observability.py`
8. **Persistence**: async SQLAlchemy models in `src/debrief_agent/models/`
9. **UI**: `src/ui/streamlit_app.py`


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
ANALYSIS_RUBRICS=overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt
DEBRIEF_AGENT_MODEL=gpt-5-mini
DEBRIEF_AGENT_LOG_RAG_CHUNKS=false
```

If you use Langfuse, set the standard Langfuse environment variables for your
instance before starting the app.

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

These CLIs import `debrief_agent.rag.ingestion.bootstrap_qdrant.ensure_collection`
and use the shared Qdrant collection from `QDRANT_COLLECTION_NAME`.

### 1) Sales frameworks markdown ingestion

Module: `src/debrief_agent/rag/ingestion/ingest_pdf_documents.py`

Reads processed markdown files from `src/data/knowledge_base/sales_frameworks`.

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

Default paths convert `src/data/knowledge_base/company_playbooks/Sales_Playbook.pdf`
to `src/data/knowledge_base/company_playbooks/Sales_Playbook.md`.

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
- `had_refusal`

## Project Structure

```text
sales-call-debrief-agent/
├── migrations/
├── src/
│   ├── data/
│   │   ├── knowledge_base/
│   │   │   ├── call_examples/
│   │   │   ├── coaching_guides/
│   │   │   ├── company_playbooks/
│   │   │   └── sales_frameworks/
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
│   │   │   ├── embeddings/
│   │   │   ├── ingestion/
│   │   │   ├── loaders/
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
- **`uv: command not found`**
  - Install `uv`, restart shell, verify with `uv --version`.
