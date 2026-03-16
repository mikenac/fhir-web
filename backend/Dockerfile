# backend/Dockerfile
# Builds the FastAPI backend image for local Docker Compose development.
#
# Build context is the `backend/` directory (set in docker-compose.yml).

# ---- Base image -------------------------------------------------------------
# python:3.13-slim is a minimal Debian image with Python 3.13 pre-installed.
# "slim" omits documentation and test files, keeping the image small.
FROM python:3.13-slim

# ---- System dependencies ----------------------------------------------------
# git is required because one of our Python dependencies (python-fhir-client)
# is installed directly from a GitHub repository.  Without git, `uv sync` will
# fail when it tries to clone the repo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*
# --no-install-recommends: skip optional packages to keep the image lean.
# rm -rf /var/lib/apt/lists/*: delete the package index cache after install.

# ---- Install uv -------------------------------------------------------------
# uv is a fast Python package manager (written in Rust) that understands
# pyproject.toml natively.  We copy just the binary from the official image
# rather than running a pip install.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ---- Working directory -------------------------------------------------------
WORKDIR /app

# ---- Dependency files first (layer caching) ---------------------------------
# Copy both pyproject.toml AND uv.lock before the rest of the source so
# Docker can cache the `uv sync` layer.  The layer is only rebuilt when either
# of these files changes, not on every source-code change.
COPY pyproject.toml uv.lock ./

# ---- Install Python dependencies --------------------------------------------
# --frozen: requires the lockfile to exist and refuses to update it, ensuring
#   every build uses the exact same pinned versions (reproducible builds).
#   This is especially important for the git-sourced python-fhir-client dep.
# --no-dev: skip development/test dependencies in the production image.
# uv creates a virtual environment at /app/.venv automatically.
RUN uv sync --frozen --no-dev

# ---- Copy application source ------------------------------------------------
# Comes after dependency install so code changes don't invalidate the
# (slow) dependency layer above.
COPY . .

# ---- Runtime data directory -------------------------------------------------
# The DuckDB database file is stored here.  This path is mounted as a named
# volume in docker-compose.yml so data persists between container restarts.
RUN mkdir -p /app/data

# ---- Network port -----------------------------------------------------------
EXPOSE 8000

# ---- Start the application --------------------------------------------------
# `uv run` activates the virtual environment and then runs the command.
# --host 0.0.0.0  binds to all interfaces so Docker can forward traffic.
# --port 8000     matches the EXPOSE above and the compose port mapping.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
