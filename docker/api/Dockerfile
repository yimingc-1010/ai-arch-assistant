FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber / lxml / chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packages in dependency order
COPY packages/core   packages/core
COPY packages/law    packages/law
COPY packages/rag    packages/rag
COPY packages/api    packages/api
COPY cli             cli

# Install in dependency order (core first, api last)
RUN pip install --no-cache-dir -e packages/core \
    && pip install --no-cache-dir -e packages/law \
    && pip install --no-cache-dir -e "packages/rag[all]" \
    && pip install --no-cache-dir -e packages/api

EXPOSE 8000

CMD ["uvicorn", "autocrawler_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
