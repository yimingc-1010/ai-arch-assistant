# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoCrawler is a multi-package Python monorepo for automatic web crawling. It selects between HTML parsing and API fetching strategies based on URL analysis. The project includes a core crawling engine, law-specific scraper plugin, CLI tool, a REST API, and a RAG system for law PDFs.

## Commands

```bash
# Install all packages in dev mode
make install-dev

# Install core only (no law plugin)
make install-core

# Install RAG system
make install-rag

# Run all tests
make test

# Run tests for a specific package
make test-core
make test-law
make test-rag

# Run a single test
pytest packages/core/tests/test_analyzer.py::TestURLAnalyzer::test_api_pattern_detection -v

# Run CLI
autocrawler https://example.com -v
autocrawler https://example.com -s html       # force HTML strategy
autocrawler https://example.com -o out.json   # save to file

# lawrag CLI
lawrag ingest 建築法.pdf --law-name 建築法 -v
lawrag query "申請建造執照需要哪些文件？" --law 建築法
lawrag list

# Start API dev server
make dev-api

# Clean build artifacts
make clean
```

## Architecture

```
ai-arch-assistant/
├── packages/
│   ├── core/            # Core crawling engine (autocrawler-core)
│   │   └── src/autocrawler/
│   │       ├── registry.py      # Strategy plugin registration
│   │       ├── analyzer.py      # URLAnalyzer (strategy selection)
│   │       ├── html_scraper.py  # BeautifulSoup HTML extraction
│   │       ├── api_scraper.py   # JSON/XML API response handling
│   │       └── crawler.py       # AutoCrawler orchestrator
│   ├── law/             # Law-specific scraper plugin (autocrawler-law)
│   │   └── src/autocrawler_law/
│   │       ├── scrapers.py      # MojLawScraper, ArkitekiScraper
│   │       ├── exporter.py      # CSV export
│   │       └── plugin.py        # Registers law strategies with core
│   ├── rag/             # RAG system for law PDFs (lawrag)
│   │   └── src/lawrag/
│   │       ├── config.py        # Env var config (LAWRAG_*)
│   │       ├── providers/       # Embedding & LLM providers (Voyage, Anthropic, OpenAI)
│   │       ├── pdf/             # PDF extraction & article-aware chunking
│   │       ├── store/           # ChromaDB vector store
│   │       ├── pipeline/        # Ingestor & Retriever
│   │       └── cli/             # lawrag CLI
│   └── api/             # FastAPI REST API (autocrawler-api)
│       └── src/autocrawler_api/
│           └── routes/
│               ├── health.py    # GET /health
│               └── rag.py       # POST /rag/ingest, POST /rag/query, GET /rag/documents
├── cli/                 # CLI tool (autocrawler-cli)
└── Makefile             # Dev commands
```

### Strategy Selection Flow
1. `URLAnalyzer.analyze()` checks registered strategy plugins first (via `registry.py`)
2. If no plugin matches, scores the URL based on path patterns, subdomain, Content-Type, API probing
3. Score >= 0.6 → API strategy; otherwise → HTML strategy
4. If API strategy fails, falls back to HTML (`html_fallback`)

### Plugin System
- `packages/core/src/autocrawler/registry.py` provides `register_strategy()` and `detect_strategy()`
- `packages/law/src/autocrawler_law/plugin.py` registers law site detectors
- CLI auto-loads the law plugin if `autocrawler-law` is installed

### Package Dependencies
```
core ← law
     ← cli
     ← api (lawrag optional)
rag  (independent)
```

### RAG System (lawrag)
- **Embedding**: Voyage AI `voyage-law-2` (asymmetric: `input_type="document"` for ingest, `input_type="query"` for retrieval)
- **LLM**: Anthropic `claude-sonnet-4-6`
- **Vector DB**: ChromaDB (local persistent), per-law collection with SHA256-hashed names
- **PDF chunking**: article-aware (`第X條`) primary strategy, sliding-window fallback

## Testing

Tests use `responses` library to mock HTTP requests. Tests are co-located with packages:
- `packages/core/tests/` — TestURLAnalyzer, TestHTMLScraper, TestAPIScraper, TestAutoCrawler, TestErrorHandling
- `packages/law/tests/` — TestMojLawScraper, TestArkitekiScraper, TestLawExporter, TestLawSiteDetection
- `packages/rag/tests/` — TestChunker, TestReader, TestStore, TestIngestor, TestRetriever, TestProviders
