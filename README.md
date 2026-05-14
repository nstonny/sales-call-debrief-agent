# Sales Call Debrief Agent

LLM-powered pipeline for analyzing sales call transcripts and generating structured debrief insights for sales coaching and CRM workflows.

## Project Status

> 🚧 **This project is currently in active development.**

The `main` branch is kept as a stable/public snapshot and may not include the newest features.

The latest progress, active implementation work, and ongoing updates are in the **`dev`** branch.

## Branches

- `main`: stable baseline
- `dev`: active development branch (latest work)

## Current Scope (High-Level)

This project is being built to:
- ingest sales call transcripts,
- extract key call metadata,
- generate structured LLM-based debrief analysis,
- support rubric-based experimentation.

## Quick Start (Main Branch)

### Prerequisites

- Python 3.13+
- `uv` installed

Install `uv` if needed:

```zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

```zsh
git clone https://github.com/nstonny/sales-call-debrief-agent.git
cd sales-call-debrief-agent
uv venv
source .venv/bin/activate
uv sync
```

## Want the Latest Development Version?

Switch to the `dev` branch:

```zsh
git checkout dev
```

(If needed, fetch first: `git fetch origin`)

## Notes

As development is ongoing, documentation and architecture may evolve quickly in `dev`.

