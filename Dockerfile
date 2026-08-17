# Single image, reused by every app service in docker-compose.yml with a
# different `command`: api (uvicorn), ui (streamlit), migrate (alembic), seed.
#
# Two stages. The builder resolves and installs dependencies; the runtime stage
# starts clean and receives only the finished /app. This keeps the uv binary
# (~50MB) and the build cache out of the shipped image, and — more importantly —
# lets the venv arrive already owned by the runtime user. A `chown -R` after the
# fact would rewrite every file's metadata and force Docker to duplicate the
# entire 841MB venv into a second layer.

# --------------------------------------------------------------------------- #
# Stage 1: build the virtualenv
# --------------------------------------------------------------------------- #
FROM python:3.13-slim AS builder

# uv, copied from its official distroless image. Pinned rather than :latest so
# a rebuild six months from now resolves the same dependency solver.
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Dependencies are installed before the source is copied, so editing a .py file
# does not invalidate this layer and reinstall the whole tree.
#
# README.md is required here: pyproject.toml:5 declares readme = "README.md",
# and the build backend reads it while resolving project metadata.
#
# --no-install-project installs only dependencies, not debrief_agent itself
# (its source isn't copied yet). --no-dev skips the dev group, whose `jupyter`
# entry would add >100MB of notebook machinery; tests run natively via
# `uv run pytest`.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY src/ ./src/

# Installs debrief_agent itself, as an editable install pointing at /app/src.
# The runtime stage keeps the identical /app path, so that pointer stays valid —
# and it is what lets the compose bind-mount of ./src take effect with no rebuild.
RUN uv sync --frozen --no-dev

# --------------------------------------------------------------------------- #
# Stage 2: runtime
# --------------------------------------------------------------------------- #
FROM python:3.13-slim

# Containers run as root by default; a stray write inside the bind-mounted
# ./src would then land on the host owned by root.
#
# /app is created here with appuser ownership rather than left to WORKDIR, which
# would create it as root. `COPY --chown` below sets ownership on the entries it
# copies but not on their parent directory, so without this the ingestion CLIs
# cannot mkdir /app/experiments.local for their trace output.
RUN useradd --create-home --uid 10001 appuser \
    && install -d -o appuser -g appuser /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# One layer, already owned by appuser — no post-hoc chown pass.
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

# Overridden per service in docker-compose.yml. Present so `docker run` against
# this image alone does something sensible.
CMD ["uvicorn", "debrief_agent.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
