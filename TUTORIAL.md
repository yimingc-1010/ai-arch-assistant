# Auto-Crawler Tutorial

A Python web scraper that automatically selects the best strategy (HTML, API, or Law) based on URL analysis.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Usage Examples](#usage-examples)
5. [Testing Guide](#testing-guide)
6. [Module Reference](#module-reference)

---

## Installation

```bash
# Clone or navigate to project
cd auto-crawler

# Install dependencies
pip install -r requirements.txt
```

**Dependencies:**
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `lxml` - Fast HTML parser
- `pytest` - Testing framework
- `responses` - HTTP mocking for tests

---

## Quick Start

### Basic Usage

```bash
# Crawl any URL (auto-detects strategy)
python crawler.py "https://example.com"

# Verbose mode (shows strategy selection)
python crawler.py "https://example.com" -v

# Save output to file
python crawler.py "https://example.com" -o output.json

# Force specific strategy
python crawler.py "https://example.com" -s html
python crawler.py "https://api.example.com/data" -s api
```

### Law Scraping (Taiwan Legal Databases)

```bash
# Scrape law from 全國法規資料庫
python crawler.py "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109" -v

# Scrape law from ArkiTeki
python crawler.py "https://arkiteki.com/term/總則編" -v

# Export as CSV
python crawler.py "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109" --csv -o law.csv
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        crawler.py                           │
│                      (AutoCrawler)                          │
│                    Main Entry Point                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     url_analyzer.py                         │
│                      (URLAnalyzer)                          │
│              Analyzes URL → Selects Strategy                │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┼───────────┬───────────┐
          ▼           ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  'html'  │ │  'api'   │ │'law_moj' │ │'law_ark' │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │            │
         ▼            ▼            └─────┬──────┘
┌─────────────┐ ┌─────────────┐          ▼
│html_scraper │ │ api_scraper │   ┌─────────────┐
│    .py      │ │    .py      │   │ law_scraper │
└─────────────┘ └─────────────┘   │    .py      │
                                  └──────┬──────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │law_exporter │
                                  │    .py      │
                                  │ (CSV output)│
                                  └─────────────┘
```

### Strategy Selection Flow

1. **URLAnalyzer** scores the URL based on:
   - Domain detection (law sites get priority)
   - Path patterns (`/api/`, `/v1/`, `.json`)
   - Subdomain (`api.`, `data.`)
   - HEAD request Content-Type
   - API endpoint probing

2. **Strategy Assignment:**
   - `law.moj.gov.tw` → `law_moj` strategy
   - `arkiteki.com/term/*` → `law_arkiteki` strategy
   - Score >= 0.6 → `api` strategy
   - Otherwise → `html` strategy

3. **Fallback:** If API strategy fails, automatically falls back to HTML

---

## Usage Examples

### 1. Programmatic Usage

```python
from crawler import AutoCrawler, crawl

# Simple one-liner
result = crawl("https://example.com")
print(result['data']['title'])

# With options
crawler = AutoCrawler(verbose=True)
result = crawler.crawl("https://example.com", force_strategy='html')

# Multiple URLs
results = crawler.crawl_multiple([
    "https://example.com/page1",
    "https://example.com/page2",
])

# Save to file
crawler.save_json(result, "output.json")
```

### 2. Law Scraping

```python
from law_scraper import scrape_law, MojLawScraper
from law_exporter import export_csv

# Using convenience function
result = scrape_law("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

if result['success']:
    data = result['data']
    print(f"法規名稱: {data['law_name']}")
    print(f"條文數量: {len(data['articles'])}")

    # Export to CSV
    csv_content = export_csv(data)
    with open("law.csv", "w", encoding="utf-8") as f:
        f.write(csv_content)

# Using scraper class directly
scraper = MojLawScraper()
result = scraper.scrape("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")
```

### 3. Custom HTML Extraction

```python
from html_scraper import scrape_html

# With custom selectors
config = {
    'title_selector': 'h1.page-title',
    'content_selector': 'div.main-content',
    'custom_selectors': {
        'price': '.product-price',
        'author': '.author-name',
        'tags': '.tag-item',  # Multiple elements → returns list
    }
}

result = scrape_html("https://example.com/product", config)
print(result['data']['price'])
print(result['data']['tags'])  # ['tag1', 'tag2', ...]
```

### 4. API Scraping

```python
from api_scraper import scrape_api

# GET request
result = scrape_api("https://api.example.com/users")

# POST request with data
config = {
    'method': 'POST',
    'json_data': {'name': 'test', 'email': 'test@example.com'},
    'headers': {'Authorization': 'Bearer token123'},
}
result = scrape_api("https://api.example.com/users", config)

# Check pagination
if result['pagination']:
    print(f"Next page: {result['pagination'].get('next')}")
```

---

## Testing Guide

### Run All Tests

```bash
pytest -v
```

### Test by Module

| Module | Test Command |
|--------|--------------|
| URL Analyzer | `pytest test_crawler.py::TestURLAnalyzer -v` |
| HTML Scraper | `pytest test_crawler.py::TestHTMLScraper -v` |
| API Scraper | `pytest test_crawler.py::TestAPIScraper -v` |
| Auto Crawler | `pytest test_crawler.py::TestAutoCrawler -v` |
| Error Handling | `pytest test_crawler.py::TestErrorHandling -v` |
| MOJ Law Scraper | `pytest test_law_scraper.py::TestMojLawScraper -v` |
| ArkiTeki Scraper | `pytest test_law_scraper.py::TestArkitekiScraper -v` |
| Law Exporter | `pytest test_law_scraper.py::TestLawExporter -v` |

### Test Single Function

```bash
pytest test_crawler.py::TestURLAnalyzer::test_api_pattern_detection -v
```

### Test with Coverage

```bash
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```

---

## Module Reference

### crawler.py

| Class/Function | Description |
|----------------|-------------|
| `AutoCrawler(verbose=False)` | Main crawler class |
| `AutoCrawler.crawl(url, force_strategy=None)` | Crawl single URL |
| `AutoCrawler.crawl_multiple(urls)` | Crawl multiple URLs |
| `AutoCrawler.to_json(data, pretty=True)` | Convert to JSON string |
| `AutoCrawler.save_json(data, filepath)` | Save to JSON file |
| `crawl(url, **kwargs)` | Convenience function |

### url_analyzer.py

| Class/Function | Description |
|----------------|-------------|
| `URLAnalyzer()` | URL analysis class |
| `URLAnalyzer.analyze(url)` | Returns strategy recommendation |
| `analyze_url(url)` | Convenience function |

**Strategies:** `'html'`, `'api'`, `'law_moj'`, `'law_arkiteki'`

### html_scraper.py

| Class/Function | Description |
|----------------|-------------|
| `HTMLScraper()` | HTML parsing class |
| `HTMLScraper.scrape(url, config=None)` | Scrape HTML page |
| `scrape_html(url, config=None)` | Convenience function |

**Extracted Data:** `title`, `description`, `keywords`, `headings`, `links`, `images`, `text_content`, `meta`, `structured_data`

### api_scraper.py

| Class/Function | Description |
|----------------|-------------|
| `APIScraper()` | API fetching class |
| `APIScraper.scrape(url, config=None)` | Fetch API endpoint |
| `APIScraper.discover_api(base_url)` | Auto-discover API endpoints |
| `scrape_api(url, config=None)` | Convenience function |

**Config Options:** `method`, `headers`, `params`, `data`, `json_data`, `auth`

### law_scraper.py

| Class/Function | Description |
|----------------|-------------|
| `LawScraper` | Abstract base class |
| `MojLawScraper()` | 全國法規資料庫 scraper |
| `ArkitekiScraper()` | ArkiTeki scraper |
| `get_law_scraper(url)` | Get appropriate scraper for URL |
| `scrape_law(url)` | Convenience function |

**Extracted Data:**
```python
{
    'source': 'law.moj.gov.tw',
    'law_name': '建築法',
    'pcode': 'D0070109',
    'last_modified': '民國 111 年 05 月 11 日',
    'chapters': [{'number': '第 一 章', 'title': '總則'}],
    'articles': [{
        'number': '第 1 條',
        'chapter': '第 一 章 總則',
        'content': '...',
        'items': ['一、...', '二、...']
    }]
}
```

### law_exporter.py

| Function | Description |
|----------|-------------|
| `export_csv(law_data)` | Export to CSV string |
| `export_csv_file(law_data, filepath)` | Export to CSV file |
| `export_detailed_csv(law_data)` | Export with extra columns |

---

## Output Formats

### JSON Output (Default)

```json
{
  "url": "https://example.com",
  "timestamp": "2024-01-01T00:00:00Z",
  "strategy_analysis": {
    "strategy": "html",
    "confidence": 0.8,
    "reasons": ["Content-Type is HTML"]
  },
  "strategy_used": "html",
  "success": true,
  "data": { ... },
  "error": null
}
```

### CSV Output (Law Only)

```csv
"條號","章節","條文內容"
"第 1 條","第 一 章 總則","為實施建築管理..."
"第 2 條","第 一 章 總則","主管建築機關..."
```

---

## Troubleshooting

### Common Issues

1. **Import Error**
   ```bash
   pip install -r requirements.txt
   ```

2. **Encoding Issues (Chinese)**
   - The scrapers auto-detect encoding
   - CSV exports use `utf-8-sig` for Excel compatibility

3. **Network Timeout**
   - Default timeout is 30 seconds
   - Check network connection

4. **Empty Results**
   - Check if the website structure has changed
   - Use `-v` flag to see strategy selection details

### Debug Mode

```bash
# Verbose output shows strategy selection
python crawler.py "https://example.com" -v

# Check what strategy would be used
python -c "from url_analyzer import analyze_url; print(analyze_url('https://example.com'))"
```
