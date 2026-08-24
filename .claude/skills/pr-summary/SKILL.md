---
name: pr-summary
description: Writes the PR title and body for this repo when opening a pull request — repo-specific reviewer callouts and manual-verification notes layered on the standard Summary template. Use when creating a pull request or running `gh pr create` in this project.
---

Draft the PR title and body before running `gh pr create`. Only actually
open the PR when the user has asked for that — this skill governs content,
not whether to open it.

## Steps

1. **Inspect the full change set.** Run `git status`, `git diff main...HEAD`,
   and `git log main..HEAD` — every commit since diverging from `main`, not
   just the latest — so the summary reflects the whole PR.

2. **Title**: `type(scope): imperative subject`, same type/scope vocabulary
   as `.claude/skills/commit-message/SKILL.md` (`feat`, `fix`, `docs`,
   `build`, `refactor`, `test`, `chore`, `ci`, `perf`; scope inferred from
   the changed path), under ~70 characters.

3. **Body — `## Summary`**: 1–3 bullets covering what changed and why,
   grouped by concern if the PR spans multiple areas.

4. **Body — `## Test plan`**: don't restate `ruff check` / `ruff format` /
   `pytest` — those are the CI `lint` and `test` jobs, and GitHub already
   shows them as status checks on the PR, so repeating them here is noise.
   Use this section only for verification CI *can't* show as a checkmark:
   - manual/UI checks actually performed (e.g. "uploaded a transcript via
     the Streamlit UI and confirmed the analysis fields populated")
   - the docker boot check, when the diff touches `Dockerfile`,
     `docker-compose.yml`, `pyproject.toml`, or `uv.lock` — the CI `docker`
     job covers this automatically, but it isn't in CLAUDE.md's local
     command list, so call out that it was considered:
     `- [ ] docker build -t debrief:ci . boots and exposes /api/upload`

   If no manual verification was performed and the docker case doesn't
   apply, omit the section entirely rather than filling it with restated
   CI gates.

5. **Body — `## Notes for reviewers`** (omit the whole section if none of
   these match): add one bullet per condition the diff actually touches —
   - touches `tests/` → confirm no live-service dependency was introduced
     (tests must stay offline)
   - touches `core/config.py` → flag that it raises at import time, so
     `alembic` and `pytest` both need `DATABASE_URL`/`OPENAI_API_KEY` set
   - touches `rag/ingestion/*` or `seed_all.py` → flag append-not-replace
     semantics (`add_documents` mints fresh point IDs) and confirm the
     module is registered in `seed_all.INGESTION_MODULES`
   - touches `retrieval_models.KnowledgeType` → remind that a new
     knowledge type needs all three of: the enum value, a `retrieve_*`
     tool in `rag/agent/tools.py`, and a registered ingestion module —
     `COMPANY_PLAYBOOKS` is the on-record example of what breaks when one
     of the three is skipped
   - touches the ruff `ignore` list in `pyproject.toml` → note the ignores
     are deliberate (reasons documented inline), not oversight

6. **Create the PR** via heredoc:
   ```zsh
   gh pr create --title "type(scope): subject" --body "$(cat <<'EOF'
   ## Summary
   - ...
   EOF
   )"
   ```

## Example

A PR adding a new coaching-guide ingestion source:

```
feat(rag): add objection-handling guide to coaching ingestion

## Summary
- ingest a new coaching-guide PDF covering objection handling, chunked
  with the existing coaching_guide_chunker
- no schema changes; reuses the coaching_guides knowledge type end to end

## Notes for reviewers
- touches rag/ingestion/ingest_coaching_guides.py — confirmed it's already
  registered in seed_all.INGESTION_MODULES, so `seed_all --force` picks it
  up rather than needing a separate seeding step
```
