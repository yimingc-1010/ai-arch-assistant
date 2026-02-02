# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Auto-crawler is a Python web scraper that automatically selects between HTML parsing and API fetching strategies based on URL analysis. It outputs results in JSON format.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run crawler on a URL
python crawler.py <url>
python crawler.py https://example.com/api/data -v  # verbose
python crawler.py https://example.com -s html      # force HTML strategy
python crawler.py https://example.com -o out.json  # save to file

# Run tests
pytest test_crawler.py -v

# Run a single test
pytest test_crawler.py::TestURLAnalyzer::test_api_pattern_detection -v
```

## Architecture

```
crawler.py          # Main entry point (AutoCrawler class)
    ├── url_analyzer.py   # Strategy selection (API vs HTML)
    ├── html_scraper.py   # BeautifulSoup-based HTML extraction
    └── api_scraper.py    # JSON/XML API response handling
```

**Strategy Selection Flow:**
1. `URLAnalyzer.analyze()` scores the URL based on:
   - Path patterns (`/api/`, `/v1/`, `.json`)
   - Subdomain (`api.`, `data.`)
   - HEAD request Content-Type
   - API endpoint probing
2. Score >= 0.6 → API strategy; otherwise → HTML strategy
3. If API strategy fails, falls back to HTML (`html_fallback`)

**Scraper Outputs:**
- HTML: title, meta, headings, links, images, text_content, structured_data (JSON-LD)
- API: parsed JSON/XML data, pagination info (Link headers + common fields)

## Testing

Tests use `responses` library to mock HTTP requests. Each test class covers one module:
- `TestURLAnalyzer` - pattern detection, content-type checks
- `TestHTMLScraper` - DOM extraction, custom selectors
- `TestAPIScraper` - JSON/XML parsing, pagination
- `TestAutoCrawler` - strategy auto-selection, fallback behavior
- `TestErrorHandling` - network errors, invalid responses
