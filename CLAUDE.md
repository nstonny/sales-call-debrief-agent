# CLAUDE.md

Operational notes for working in this repo. Setup, architecture and API usage are
in `README.md` — this file covers what that doesn't: the conventions and the traps.

## Commands

```zsh
uv run pytest                                       # 200 tests, fully offline
uv run pytest --cov=debrief_agent                   # coverage (~38%)
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run alembic upgrade head
uv run uvicorn debrief_agent.app.main:app --reload  # API  -> :8000
uv run streamlit run src/ui/streamlit_app.py        # UI   -> :8501
uv run python -m debrief_agent.rag.ingestion.seed_all [--force]
docker compose up                                   # whole stack, auto-seeded
```

Before committing, run the three gates CI runs:

```zsh
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run pytest
```

## Conventions

- **Absolute `debrief_agent.*` imports only.** The package is installed editable
  and `pythonpath = ["src"]` is set under `[tool.pytest.ini_options]`.
- **4-space indentation**, enforced by `ruff format`.
- **`logger = logging.getLogger(__name__)`, not `print`.** One known exception:
  `rag/agent/tools.py:72,85,98` still use `print("TOOL CALLED: ...")`. They predate
  the rule and no selected ruff rule catches them; don't copy the pattern.
- **Commit messages**: conventional subject, blank line, `- ` bullets wrapped at
  ~72 characters. `git log` shows the established shape.

## Rules that bite

1. **Tests must stay offline.** `tests/conftest.py` deliberately stubs the OpenAI
   client and Qdrant points. Never add a test needing a live service — CI runs with
   nothing but placeholder credentials.
2. **`core/config.py` raises at import.** A missing `DATABASE_URL` or
   `OPENAI_API_KEY` raises `ValueError` *while importing*, so even `alembic` and
   `pytest` need both set. Placeholder values are fine; nothing connects.
3. **Ingestion appends, never replaces.** `get_vector_store().add_documents(...)`
   mints fresh point IDs, so re-running an ingestion CLI duplicates every chunk
   rather than updating it. Use `seed_all`, which skips when the collection is
   non-empty, or `seed_all --force` to drop and rebuild.
4. **The ruff `ignore` list is deliberate — don't "clean it up".** `RUF001-003`
   are intentional en dashes in prose. `UP042` is skipped because `StrEnum` changes
   what `str(member)` returns, which would alter serialization. The
   `flake8-bugbear` allowlist exists because FastAPI's `Depends`/`File`/`Form`/
   `Query` idiom trips `B008`. Reasons are in `pyproject.toml`.
5. **Two model variables, not one.** `DEBRIEF_ANALYSIS_MODEL` (default
   `gpt-5-mini`) drives the tool-calling agent; `DEBRIEF_EXTRACTION_MODEL`
   (default `gpt-4.1-mini`) drives the structured parse. Provider is OpenAI.
6. **Docker specifics.** The image builds with `uv sync --no-dev`, so anything in
   the dev group — including `markitdown` — is absent at runtime. Compose publishes
   Postgres on host **5433** to avoid clashing with a native install, and
   bind-mounts `./src` for live reload.

## Where things go

**A new knowledge type needs three edits:**

1. the `KnowledgeType` enum in `rag/retrieval/retrieval_models.py`
2. a `retrieve_*` tool in `rag/agent/tools.py`
3. an ingestion module in `rag/ingestion/`, registered in
   `seed_all.INGESTION_MODULES`

`COMPANY_PLAYBOOKS` is declared but has neither (2) nor (3), which is exactly why
retrieval against it returns nothing — a worked example of the failure mode.

**A new LLM service** goes in `rag/agent/services/`, paired with a prompt builder
in `rag/agent/prompts/` and a Pydantic schema in `schemas/`. Follow
`services/extraction.py` and `services/analysis.py`; they mirror each other
deliberately.
