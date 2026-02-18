# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoCrawler is a multi-package Python monorepo for automatic web crawling. It selects between HTML parsing and API fetching strategies based on URL analysis. The project includes a core crawling engine, law-specific scraper plugin, CLI tool, and scaffolds for a REST API, database layer, scheduler, and Next.js frontend.

## Commands

```bash
# Install all packages in dev mode
make install-dev

# Install core only (no law plugin)
make install-core

# Run all tests
make test

# Run tests for a specific package
make test-core
make test-law

# Run a single test
pytest packages/core/tests/test_analyzer.py::TestURLAnalyzer::test_api_pattern_detection -v

# Run CLI
autocrawler https://example.com -v
autocrawler https://example.com -s html       # force HTML strategy
autocrawler https://example.com -o out.json   # save to file

# Start API dev server (requires packages/api deps)
make dev-api

# Start Next.js frontend
make dev-web

# Clean build artifacts
make clean
```

## Architecture

```
ai-arch-assistant/
├── packages/
│   ├── shared/          # Shared types, config, utilities (autocrawler-shared)
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
│   ├── db/              # Database layer scaffold (autocrawler-db)
│   ├── api/             # FastAPI REST API scaffold (autocrawler-api)
│   └── scheduler/       # Background job scheduler scaffold (autocrawler-scheduler)
├── cli/                 # CLI tool (autocrawler-cli)
├── apps/
│   └── web/             # Next.js frontend scaffold
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
shared ← core ← law
              ← cli
              ← api ← db
              ← scheduler ← db
```

## Testing

Tests use `responses` library to mock HTTP requests. Tests are co-located with packages:
- `packages/core/tests/` — TestURLAnalyzer, TestHTMLScraper, TestAPIScraper, TestAutoCrawler, TestErrorHandling
- `packages/law/tests/` — TestMojLawScraper, TestArkitekiScraper, TestLawExporter, TestLawSiteDetection
