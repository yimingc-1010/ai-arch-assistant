# GitHub as Law PDF Source — Design Spec

**Date:** 2026-03-13
**Status:** Approved

---

## Overview

Use the existing `ai-arch-assistant` GitHub repository as the authoritative source for law regulation PDFs. PDFs are committed directly into `data/laws/`. A sync pipeline detects changed files (via SHA256 content hash) and re-ingests only what has changed into ChromaDB. Sync is triggered by manual CLI, daily schedule, or GitHub webhook on push.

---

## Goals

- Store law PDFs in `data/laws/` under version control (Git commit, plain files).
- Detect changes via SHA256 content hash comparison against the existing ChromaDB index metadata — no new database required.
- Support three sync trigger modes: manual CLI (`lawrag sync`), daily cron (GitHub Actions schedule), and GitHub push webhook (`POST /rag/sync`).
- Keep the `PDFSource` abstraction open for Git LFS migration without interface changes.

## Non-Goals

- Storing vector embeddings on GitHub (ChromaDB remains local).
- Using GitHub API or GitHub Releases for PDF hosting.
- Automatic law name inference from `manifest.json` (law name is inferred from filename, same as existing `Ingestor`).

---

## Directory Structure

```
ai-arch-assistant/
├── data/
│   └── laws/                        # Law PDF repository (git-committed)
│       ├── 建築法.pdf
│       ├── 都市計畫法.pdf
│       └── ...
├── packages/
│   ├── rag/
│   │   └── src/lawrag/
│   │       └── sync/                # New module
│   │           ├── __init__.py
│   │           ├── scanner.py       # PDFSource protocol + LocalPDFScanner
│   │           └── manager.py       # SyncManager: scan → diff → ingest
│   └── api/
│       └── src/autocrawler_api/
│           └── routes/
│               └── sync.py          # POST /rag/sync webhook endpoint
└── .github/
    └── workflows/
        └── sync-laws.yml            # Push + scheduled trigger
```

---

## Components

### `lawrag/sync/scanner.py`

Defines a `PDFSource` protocol and the concrete `LocalPDFScanner` implementation.

```python
@dataclass
class PDFEntry:
    path: Path
    law_name: str      # Inferred from filename stem (same logic as Ingestor)
    content_hash: str  # SHA256 hex digest of file bytes

class PDFSource(Protocol):
    def list_pdfs(self) -> List[PDFEntry]: ...

class LocalPDFScanner:
    """Scans a local directory for *.pdf files."""
    def __init__(self, laws_dir: Path) -> None: ...
    def list_pdfs(self) -> List[PDFEntry]: ...
```

**Change detection:** `content_hash` is compared against `LawChromaStore.get_index_metadata(law_name)["content_hash"]`. A `None` stored hash (first ingest from PDF with no web-scrape hash) is treated as "unknown" — the scanner triggers re-ingest to establish the hash baseline.

**LFS extension point:** A future `GitHubLFSScanner` class implements `PDFSource` by calling the GitHub Contents API for blob SHAs. `SyncManager` accepts any `PDFSource` and requires no changes.

---

### `lawrag/sync/manager.py`

Coordinates the full sync flow.

```python
@dataclass
class SyncResult:
    ingested: List[str]   # Law names successfully ingested
    skipped: List[str]    # Unchanged, skipped
    errors: List[str]     # Law names that failed with error message

class SyncManager:
    def __init__(self, source: PDFSource, store: LawChromaStore,
                 embedder: EmbeddingProvider) -> None: ...

    def run(self, force: bool = False, verbose: bool = False) -> SyncResult:
        """
        1. source.list_pdfs() → List[PDFEntry]
        2. For each entry:
           a. store.get_index_metadata(law_name) → existing hash
           b. If force or hash differs (or no existing hash): Ingestor.ingest(entry.path)
           c. Else: skip
        3. Return SyncResult
        """
```

**Error handling:** Each PDF is ingested independently. A failure on one law is caught, recorded in `SyncResult.errors`, and the loop continues. The webhook endpoint returns HTTP 207 (multi-status) if any errors occurred.

---

### `autocrawler_api/routes/sync.py`

New FastAPI router mounted at `/rag/sync`.

```
POST /rag/sync
Headers:
  X-Hub-Signature-256: sha256=<hmac-sha256 of request body using GITHUB_WEBHOOK_SECRET>
Body: GitHub push event JSON (payload is verified but not parsed — sync is always full-scan)

Responses:
  200 OK          { "ingested": [...], "skipped": [...], "errors": [] }
  207 Multi-Status { "ingested": [...], "skipped": [...], "errors": [...] }
  401 Unauthorized  (invalid or missing HMAC signature)
  500 Internal Server Error (sync could not start)
```

**Security:** HMAC-SHA256 signature verified using `hmac.compare_digest` before any processing. If `GITHUB_WEBHOOK_SECRET` is not set, the endpoint rejects all requests with 500.

**Async behaviour:** The sync runs synchronously within the request for simplicity. If ingest time becomes a concern, this can be moved to a background task (FastAPI `BackgroundTasks`) without changing the interface.

---

### CLI: `lawrag sync`

New subcommand added to `lawrag/cli/main.py`.

```
lawrag sync [--laws-dir PATH] [--force] [-v]

Options:
  --laws-dir PATH   Directory to scan for PDFs (default: LAWRAG_LAWS_DIR or ./data/laws)
  --force           Re-ingest all PDFs regardless of hash match
  -v, --verbose     Print per-file progress
```

New config function: `get_laws_dir() -> str` in `lawrag/config.py`, reads `LAWRAG_LAWS_DIR` env var (default `./data/laws`).

---

### GitHub Actions: `.github/workflows/sync-laws.yml`

```yaml
name: Sync Law PDFs

on:
  push:
    paths:
      - 'data/laws/**'
  schedule:
    - cron: '0 2 * * *'   # Daily at 02:00 UTC

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger sync webhook
        env:
          DEPLOY_URL: ${{ secrets.DEPLOY_URL }}
          WEBHOOK_SECRET: ${{ secrets.GITHUB_WEBHOOK_SECRET }}
        run: |
          BODY=''
          SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')"
          curl -f -X POST "$DEPLOY_URL/rag/sync" \
            -H "Content-Type: application/json" \
            -H "X-Hub-Signature-256: $SIG" \
            -d "$BODY"
```

**Required GitHub Secrets:** `DEPLOY_URL` (e.g. `https://yourdomain.com`), `GITHUB_WEBHOOK_SECRET`.

---

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `LAWRAG_LAWS_DIR` | `./data/laws` | Local directory scanned for PDF files |
| `GITHUB_WEBHOOK_SECRET` | *(required)* | HMAC secret shared between GitHub Actions and the API |
| `LAWRAG_CHROMA_DIR` | `./data/chroma` | ChromaDB persist directory (unchanged) |

---

## Data Flow Summary

```
PDF committed to data/laws/ on GitHub
        │
        ▼
GitHub Actions detects push to data/laws/**
        │
        ▼
POST /rag/sync  (with HMAC signature)
        │
   Verify signature
        │
   SyncManager.run()
        │
   LocalPDFScanner.list_pdfs()
   → PDFEntry(path, law_name, content_hash) per file
        │
   For each PDFEntry:
     get_index_metadata(law_name) → stored content_hash
     content_hash differs? ──yes──► Ingestor.ingest(path)
                           ──no───► skip
        │
   Return SyncResult { ingested, skipped, errors }
```

---

## Future: Git LFS Migration Path

When the number or size of PDFs warrants LFS:

1. Run `git lfs track "data/laws/*.pdf"` — adds `.gitattributes`.
2. Implement `GitHubLFSScanner(PDFSource)` using GitHub Contents API blob SHAs as change signal.
3. Pass `GitHubLFSScanner` to `SyncManager` — no other code changes.

---

## Testing

| Test | Approach |
|---|---|
| `LocalPDFScanner` | Create temp dir with sample PDFs; assert `PDFEntry` list and SHA256 values |
| `SyncManager` skip | Mock store returning matching hash; assert no `Ingestor.ingest` calls |
| `SyncManager` ingest | Mock store returning different hash; assert `Ingestor.ingest` called once |
| `SyncManager` error handling | Mock `Ingestor.ingest` raising exception; assert other PDFs still processed |
| `/rag/sync` auth | Valid + invalid HMAC signatures; assert 200/401 |
| `/rag/sync` result codes | Mix of success/error ingest; assert 207 |
