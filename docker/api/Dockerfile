FROM python:3.11-slim

WORKDIR /app

# System deps — cached unless this RUN changes
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# --- Dependency layer (cached as long as pyproject.toml files are unchanged) ---
# Copy only manifests so Docker can cache pip install separately from source
COPY packages/core/pyproject.toml packages/core/
COPY packages/law/pyproject.toml  packages/law/
COPY packages/rag/pyproject.toml  packages/rag/
COPY packages/api/pyproject.toml  packages/api/
COPY cli/pyproject.toml           cli/

# Stub __init__.py files so editable installs can resolve package metadata
RUN mkdir -p packages/core/src/autocrawler \
    && touch packages/core/src/autocrawler/__init__.py \
    && mkdir -p packages/law/src/autocrawler_law \
    && touch packages/law/src/autocrawler_law/__init__.py \
    && mkdir -p packages/rag/src/lawrag \
    && touch packages/rag/src/lawrag/__init__.py \
    && mkdir -p packages/api/src/autocrawler_api \
    && touch packages/api/src/autocrawler_api/__init__.py \
    && mkdir -p cli/src/autocrawler_cli \
    && touch cli/src/autocrawler_cli/__init__.py

RUN pip install --no-cache-dir -e packages/core \
    && pip install --no-cache-dir -e packages/law \
    && pip install --no-cache-dir -e "packages/rag[all]" \
    && pip install --no-cache-dir -e packages/api

# --- Source layer (rebuilds on every code change, but pip install above is cached) ---
COPY packages/core packages/core
COPY packages/law  packages/law
COPY packages/rag  packages/rag
COPY packages/api  packages/api
COPY cli           cli

EXPOSE 8000

CMD ["uvicorn", "autocrawler_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
