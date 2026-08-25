---
name: ingest-kb
description: Wraps this repo's four RAG ingestion CLIs in the right order, dry-run first, then verifies Qdrant collection point counts before/after. Use when seeding or re-seeding the knowledge base, or running any debrief_agent.rag.ingestion.* / document_processing command in this project.
---

Draft the ingestion plan before running anything. Only actually run
ingestion commands when the user has asked for that — this skill governs
which commands, in which order, and how to verify them, not whether to run
them; ingestion writes to Qdrant, so treat a real run like a commit or a
PR: propose it, execute on request.

## Steps

1. **Scope the change.** Identify what actually needs ingesting: a new/
   changed PDF under `sales_frameworks/`, a changed coaching-guide DOCX, a
   changed call-example transcript, a chunker code change, or a from-empty
   first seed. This decides which of steps 2–4 apply.

2. **Convert PDF → markdown first, only if needed** —
   `debrief_agent.rag.scripts.document_processing.convert_pdf_to_markdown_markitdown`.
   Skip this step entirely unless a `sales_frameworks` source PDF changed.
   **Always pass explicit `--source-pdf`/`--target-markdown` pointed at
   `sales_frameworks/...`** — never rely on the command's defaults, which
   point at `company_playbooks/Sales_Playbook.{pdf,md}`. `COMPANY_PLAYBOOKS`
   has no `retrieve_*` tool and is never registered in `seed_all` — markdown
   written there is inert, the same failure mode CLAUDE.md already flags.

3. **Dry run the three Qdrant-writing CLIs first**, in `seed_all`'s order
   (order only affects log readability — the collection is shared):
   ```zsh
   uv run python -m debrief_agent.rag.ingestion.ingest_pdf_documents --dry-run
   uv run python -m debrief_agent.rag.ingestion.ingest_coaching_guides --dry-run
   uv run python -m debrief_agent.rag.ingestion.ingest_call_examples --dry-run
   ```
   Inspect the printed chunk counts and JSONL trace before anything touches
   Qdrant.

4. **Pick the real-run strategy** based on collection state — don't just
   default to one:
   - Empty collection / first seed:
     `uv run python -m debrief_agent.rag.ingestion.seed_all`
   - Want a clean full rebuild:
     `uv run python -m debrief_agent.rag.ingestion.seed_all --force`
   - Iterating on exactly one source against an **already-populated**
     collection: flag that a direct re-run of that one CLI will append
     duplicate chunks (`add_documents` mints fresh point IDs, and there's
     no per-source delete). The only safe option is `seed_all --force`,
     not a partial re-run of the one CLI.

5. **Verify Qdrant counts before and after**, reusing the exact pattern
   already in `seed_all.collection_point_count()`:
   ```zsh
   uv run python -c "
   from debrief_agent.core.qdrant import get_sync_qdrant_client, get_sync_qdrant_collection_name
   client = get_sync_qdrant_client()
   name = get_sync_qdrant_collection_name()
   print(client.count(collection_name=name, exact=True).count)
   "
   ```
   Confirm the after-count increased relative to the before-count — or
   stayed the same if `seed_all` skipped because the collection was already
   populated, which is the expected guarded behavior, not a bug.

## Example

`seed_all`'s guarded skip path looks like this in practice (verbatim from
README.md):

```
seed-1  | Qdrant collection already holds 155 points -- skipping seed.
```

End-to-end example — adding a new coaching guide DOCX to an already-seeded
collection:

```zsh
uv run python -c "... print(client.count(...).count) ..."   # before: 155
uv run python -m debrief_agent.rag.ingestion.ingest_coaching_guides --dry-run
# inspect printed chunk count + trace JSONL, looks right
uv run python -m debrief_agent.rag.ingestion.seed_all --force
uv run python -c "... print(client.count(...).count) ..."   # after: 168
```
