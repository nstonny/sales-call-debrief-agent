---
name: mvp-review
description: Fast MVP code review for Python projects. Flags demo-breakers (crashes, hangs, silent failures) and basic security issues (hardcoded secrets, injection, untrusted input reaching an LLM prompt), grouped by severity, then offers to fix them on request. Use before a commit or a demo. Does not auto-edit. Not for hardening mature libraries — ignores style, type depth, and docstrings by design.
disable-model-invocation: true
---

# MVP Code Review

You are reviewing code for an **MVP** — an early product whose job is to work
reliably in a demo and not leak anything embarrassing. You are NOT hardening a
mature library. Optimise for "will this break or embarrass the author in front
of a mentor or user," not for long-term perfection.

## Scope

Review the files or directory the author names. If they name nothing, review the
code changed since the last commit (`git diff HEAD` plus untracked files); if
there is nothing uncommitted, ask which directory to scope to. Do not review
generated files, dependencies, or anything under `.venv/`, `node_modules/`,
`dist/`, or `build/`.

## What to look for

Focus on exactly two categories. Ignore style, naming, type-annotation depth,
docstring completeness, and architectural taste — those are out of scope for an
MVP review and flagging them is noise.

### 1. Demo-breakers — things that make the app crash, hang, or fail silently

- **Unhandled failure on the happy path**: network calls, file reads, API
  requests, JSON parsing, and DB queries that can raise but aren't handled, on
  the main path a demo will actually hit.
- **Silent failures**: broad `except:` / `except Exception: pass`, `.get()`
  defaults, or `contextlib.suppress` that swallow errors so the app shows wrong
  output instead of failing loudly. In a demo, a loud clear error beats a silent
  wrong answer.
- **Hangs**: external calls (HTTP, LLM APIs, DB) with no timeout; unbounded
  loops or retries; blocking calls in an async path.
- **Missing guards on external input**: assuming a response has a field, a list
  is non-empty, or a file exists, where a realistic demo input breaks the
  assumption.
- **Resource leaks that surface in a session**: files or connections opened
  without `with`, in a path that runs repeatedly.

### 2. Basic security — the things that leak in a public repo or a live demo

- **Hardcoded secrets**: API keys, tokens, passwords, connection strings in
  source. Flag anything that looks like a credential literal, and check whether
  it should be read from an environment variable instead.
- **Secrets at risk of being committed**: `.env` files or key material not
  covered by `.gitignore`; secrets printed to logs or echoed in error messages.
- **Injection**: string-formatted SQL (should be parameterised); shell commands
  built from user input (`os.system`, `subprocess` with `shell=True` and
  interpolated input); unsanitised paths from user input (path traversal).
- **Prompt injection / LLM-app surfaces** (relevant when the code calls an LLM):
  untrusted text (user input, retrieved documents, scraped content)
  concatenated directly into a system prompt or instruction context without any
  separation or note that it's untrusted. Flag it and name the entry point;
  don't try to solve prompt injection wholesale — just surface where untrusted
  data reaches the model.

## How to report

Walk the scoped code, then produce a single report. Group findings by severity:

- **🔴 Blocking** — will likely crash, hang, or leak in a demo. Fix before showing.
- **🟡 Worth fixing** — real risk but not guaranteed to surface; fix if time allows.
- **🟢 Note** — minor or situational; listed so the author is aware.

For each finding give:
- **File and line**
- **What** — one sentence on the problem
- **Why it matters for the demo** — the concrete failure or leak it causes
- **Fix** — the specific change, in one or two lines

Order findings by severity, blocking first. If a category has no findings, say
so in one line rather than padding. If the whole scope is clean, say that plainly
and stop — don't invent issues to look thorough.

## After the report — offer, don't act

End with a short offer to fix, e.g.:

> Want me to fix the 🔴 blocking issues? I can do all of them, or you can name
> the ones you want.

**Do not edit any files until the author replies asking for a fix.** When they
do, make only the changes they approve, keep each fix minimal, and don't
refactor surrounding code or touch anything outside the agreed findings.
