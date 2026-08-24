---
name: commit-message
description: Crafts git commit messages for this repo in its established conventional-commit style (type(scope): subject, blank line, "- " bullets explaining why). Use whenever writing a commit message or running `git commit` in this project.
---

Draft the commit message before running `git commit`. Only actually commit
when the user has asked for that — this skill governs message content, not
whether to commit.

## Steps

1. **Inspect the change.** Run `git status` and `git diff --staged` (fall
   back to `git diff` if nothing is staged) to understand what changed and
   why — not just which lines moved.

2. **Pick `type`** from the set this repo actually uses: `feat`, `fix`,
   `docs`, `build`, `refactor`, `test`, `chore`, `ci`, `perf`. Base it on
   the nature of the change, not the file extension.

3. **Pick `scope`** — a short noun for the affected area, inferred from the
   changed path:
   - `.claude/hooks/*`, `.claude/settings*.json` → `dev`
   - `src/debrief_agent/rag/*` → `rag`
   - `src/debrief_agent/api/*` → `api`
   - `src/ui/*` → `ui`
   - `migrations/*` → `db`
   - `pyproject.toml`, `uv.lock`, `Dockerfile*`, `docker-compose*` → `build`
   - Falls outside these → pick the closest top-level package/dir name.

4. **Subject line**: `type(scope): imperative summary`, lowercase, no
   trailing period, short enough to read in `git log --oneline`.

5. **Body**: blank line, then `- ` bullets wrapped at ~72 characters. Each
   bullet states the *why* (a constraint, a tradeoff, a bug being avoided)
   — never a mechanical restatement of the diff. Add a closing prose
   sentence only when there's a concrete, measurable outcome worth naming
   (see example below).

6. **Never add a `Co-Authored-By` trailer.** This overrides the default
   Claude Code commit template — this repo's standing convention omits it.

7. **Write via heredoc** as usual:
   ```zsh
   git commit -m "$(cat <<'EOF'
   type(scope): subject

   - bullet one
   - bullet two
   EOF
   )"
   ```

## Reference examples (verbatim from this repo's history)

```
build: move markitdown to the dev group

- markitdown is only reached by the offline PDF -> markdown conversion
  script, which imports it lazily at
  convert_pdf_to_markdown_markitdown.py:93; the api, ui, migrate and
  seed paths never load it
- it pulls magika -> onnxruntime + sympy, so as a runtime dependency it
  cost ~270MB in an image that never imports it
- the dev group keeps it installed by default for local work, while the
  Dockerfile's `uv sync --no-dev` now excludes it

Runtime image drops from 1.31GB to 1.04GB.
```

```
docs: add CLAUDE.md with project commands and conventions

- record the verified command set for tests, lint, run, migrate, seed
  and the Docker stack
- document the conventions ruff does not enforce: absolute
  debrief_agent imports, logger over print, commit message shape
- capture the traps that cost debugging time: offline-only tests,
  config.py raising at import, ingestion appending rather than
  replacing, and why the ruff ignores are deliberate
```
