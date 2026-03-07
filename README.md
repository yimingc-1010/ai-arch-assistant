# AutoCrawler

A multi-package Python monorepo for automatic web crawling with a law-specific RAG (Retrieval-Augmented Generation) system. AutoCrawler selects between HTML parsing and API fetching strategies based on URL analysis, and includes a chat interface for querying Taiwanese law regulations.

## Packages

| Package | Description |
|---|---|
| `packages/core` | Core crawling engine with strategy selection |
| `packages/law` | Law-specific scraper plugin (MoJ, Arkiteki) |
| `packages/rag` | RAG system for law PDFs (lawrag CLI) |
| `packages/api` | FastAPI REST API |
| `apps/web` | Admin UI for PDF ingestion (React + Vite) |
| `apps/lawchat` | Law chat interface (Next.js) |
| `cli/` | `autocrawler` CLI tool |

## Requirements

- Python 3.10+
- Node.js 18+
- [Voyage AI API key](https://www.voyageai.com/) (for RAG embeddings)
- [Anthropic API key](https://console.anthropic.com/) (for RAG answers)

## Installation

```bash
# Install all Python packages (core + law + cli + api)
make install-dev

# Install core only
make install-core

# Install RAG system
make install-rag

# Install frontend dependencies
make install-web
make install-lawchat
```

## Usage

### autocrawler CLI

```bash
# Auto-detect strategy and crawl
autocrawler https://example.com -v

# Force HTML strategy
autocrawler https://example.com -s html

# Save output to file
autocrawler https://example.com -o out.json
```

### lawrag CLI

```bash
# Ingest a law PDF
lawrag ingest 建築法.pdf --law-name 建築法 -v

# Query a law
lawrag query "申請建造執照需要哪些文件？" --law 建築法

# List ingested laws
lawrag list
```

## Development

```bash
# Start all services (API on :8000, web admin, lawchat on :3000)
make dev

# Start backend only
make dev-backend

# Start frontend only
make dev-frontend

# Individual services
make dev-api       # FastAPI on :8000
make dev-web       # Admin UI (Vite)
make dev-lawchat   # Law chat (Next.js) on :3000
```

## Testing

```bash
# Run all tests
make test

# Run per-package
make test-core
make test-law
make test-rag

# Run a single test
pytest packages/core/tests/test_analyzer.py::TestURLAnalyzer::test_api_pattern_detection -v
```

## Architecture

```
ai-arch-assistant/
├── packages/
│   ├── core/            # URLAnalyzer, HTML/API scrapers, AutoCrawler orchestrator
│   ├── law/             # MojLawScraper, ArkitekiScraper, law site detection plugin
│   ├── rag/             # PDF chunker, ChromaDB store, Voyage/Anthropic providers
│   └── api/             # FastAPI routes: /health, /rag/ingest, /rag/query, /rag/documents
├── apps/
│   ├── web/             # React + Vite admin UI (PDF upload)
│   └── lawchat/         # Next.js law chat interface
├── cli/                 # autocrawler CLI entry point
└── Makefile
```

### Strategy Selection

1. `URLAnalyzer.analyze()` checks registered plugin strategies first
2. If no plugin matches, scores the URL on path patterns, subdomain, Content-Type, API probing
3. Score >= 0.6 -> API strategy; otherwise -> HTML strategy
4. If API strategy fails, falls back to HTML

### RAG System

- **Embedding**: Voyage AI `voyage-law-2` (asymmetric input types for ingest vs. query)
- **LLM**: Anthropic `claude-sonnet-4-6`
- **Vector DB**: ChromaDB (local persistent), per-law collection with SHA256-hashed names
- **PDF chunking**: article-aware (`第X條`) primary, sliding-window fallback

### Environment Variables

```bash
VOYAGE_API_KEY=...              # Voyage AI key (required)
ANTHROPIC_API_KEY=...           # Anthropic key (required)
OPENAI_API_KEY=...              # OpenAI key (optional)
LAWRAG_CHROMA_DIR=./data/chroma # ChromaDB storage path (default)
LAWRAG_EMBEDDING_PROVIDER=voyage # voyage | openai (default: voyage)
LAWRAG_LLM_PROVIDER=anthropic   # anthropic | openai (default: anthropic)
```

## Docker

三個服務會一起啟動：

| 服務 | 說明 | 對外 port |
|---|---|---|
| `api` | FastAPI + RAG 後端 | 內部 :8000 |
| `lawchat` | Next.js 法規問答前端 | 內部 :3000 |
| `nginx` | 反向代理，統一入口 | **:80** |

啟動前先建立 `.env` 檔並填入 API 金鑰：

```bash
cp .env.example .env
# 編輯 .env，填入 VOYAGE_API_KEY 和 ANTHROPIC_API_KEY
```

### 常用指令

```bash
# 建立 image 並在背景啟動所有服務
docker compose up -d --build

# 啟動（已有 image，不重新建立）
docker compose up -d

# 查看所有服務狀態
docker compose ps

# 查看即時 log（所有服務）
docker compose logs -f

# 查看單一服務 log
docker compose logs -f api
docker compose logs -f lawchat

# 停止所有服務（保留 container）
docker compose stop

# 停止並移除 container
docker compose down

# 停止、移除 container 並清除 volume（會刪除 ChromaDB 資料）
docker compose down -v

# 重新建立單一服務的 image
docker compose build api
docker compose build lawchat

# 重啟單一服務
docker compose restart api
```

### 法條資料 Ingest

Docker 使用 named volume（`chroma_data`）儲存 ChromaDB，與本地開發環境隔離。容器啟動後，透過 API 將 PDF 匯入：

```bash
# 匯入單一 PDF（LAW_NAME 選填，預設使用檔名）
make docker-ingest FILE=建築法.pdf LAW_NAME=建築法

# 批次匯入目錄下所有 PDF
make docker-ingest-all DIR=./pdfs

# 直接 curl（等同 make docker-ingest）
curl -X POST http://localhost:8000/rag/ingest \
  -F "file=@建築法.pdf" \
  -F "law_name=建築法" \
  -F "embedding_provider=voyage"

# 查看已匯入的法條清單
curl http://localhost:8000/rag/documents
```

資料儲存在 named volume，`docker compose down` 不會刪除，**重新部署不需重新 ingest**。若需清除所有資料：

```bash
docker compose down -v
```

### Volume

| Volume | 說明 | 清除時機 |
|---|---|---|
| `chroma_data` | ChromaDB 向量資料 | `docker compose down -v` |
