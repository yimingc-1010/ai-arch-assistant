# GitHub as Law PDF Source — Design Spec

**Date:** 2026-03-13
**Status:** Approved

---

## Overview

Use the existing `ai-arch-assistant` GitHub repository as the authoritative source for law regulation PDFs. PDFs are committed directly into `data/laws/`. A sync pipeline detects changed files (via SHA256 content hash) and re-ingests only what has changed into ChromaDB. Sync is triggered by manual CLI, daily schedule, or GitHub Actions calling the `/rag/sync` endpoint on push.

---

## Goals

- Store law PDFs in `data/laws/` under version control (Git commit, plain files).
- Detect changes via SHA256 content hash comparison against the existing ChromaDB index metadata — no new database required.
- Support three sync trigger modes: manual CLI (`lawrag sync`), daily cron (GitHub Actions schedule), and a push-triggered call from GitHub Actions to `POST /rag/sync`.
- Keep the `PDFSource` abstraction open for Git LFS migration (see constraints in LFS section).

## Non-Goals

- Storing vector embeddings on GitHub (ChromaDB remains local).
- Using GitHub API or GitHub Releases for PDF hosting.
- Automatic law name inference from `manifest.json` (law name is inferred from filename).

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
│               └── sync.py          # POST /rag/sync endpoint
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
    law_name: str      # Inferred from filename using same logic as Ingestor._infer_law_name()
    content_hash: str  # SHA256 hex digest of raw file bytes

class PDFSource(Protocol):
    def list_pdfs(self) -> List[PDFEntry]: ...

class LocalPDFScanner:
    """Scans a local directory for *.pdf files."""
    def __init__(self, laws_dir: Path) -> None: ...
    def list_pdfs(self) -> List[PDFEntry]: ...
```

**Law name derivation:** `LocalPDFScanner` must derive `law_name` using the exact same logic as `Ingestor._infer_law_name()` — specifically, applying the suffix-stripping regex (`[_\-](sample|v\d+|\d{6,8})$`) to `path.stem` before using it as the law name. This ensures the derived name matches what is stored in the ChromaDB index. The naming convention for files in `data/laws/` should be `<law_name>.pdf` without version suffixes whenever possible.

**Change detection:** `content_hash` (SHA256 of PDF file bytes) is compared against `LawChromaStore.get_index_metadata(law_name)["content_hash"]`. A `None` stored hash triggers re-ingest to establish the baseline. After sync, the hash is stored so subsequent runs can skip unchanged files.

**LFS extension point:** A future `GitHubLFSScanner` class can implement `PDFSource` for the case where PDFs are materialised on disk via `git lfs pull`. See constraints in the LFS section.

---

### `lawrag/sync/manager.py`

Coordinates the full sync flow.

```python
@dataclass
class SyncResult:
    ingested: List[str]   # Law names successfully ingested
    skipped: List[str]    # Unchanged, skipped
    errors: List[str]     # "law_name: error message" strings

class SyncManager:
    def __init__(self, source: PDFSource, store: LawChromaStore,
                 embedder: EmbeddingProvider) -> None: ...

    def run(self, force: bool = False, verbose: bool = False) -> SyncResult:
        """
        1. source.list_pdfs() → List[PDFEntry]
        2. For each entry:
           a. store.get_index_metadata(law_name) → existing metadata
           b. If force, or stored content_hash is None, or content_hash differs:
              → ingestor.ingest(entry.path, law_name=entry.law_name,
                                content_hash=entry.content_hash)
              (Ingestor.ingest must be extended to accept and forward content_hash)
           c. Else: skip
        3. Return SyncResult
        """
```

**`Ingestor.ingest()` extension required:** The existing `Ingestor.ingest()` always stores `content_hash=None`. For the skip logic to work correctly after the first sync, `Ingestor.ingest()` must be extended with an optional `content_hash: Optional[str] = None` parameter **and** the hardcoded `content_hash=None` in the call to `_embed_and_store()` (line 119) must be replaced with the caller-supplied value. When provided by `SyncManager`, this value is forwarded to `_embed_and_store()` and stored in the ChromaDB index.

**Error handling:** Each PDF is ingested independently inside a try/except. A failure on one law is recorded in `SyncResult.errors` as `"law_name: error message"` and the loop continues.

---

### `autocrawler_api/routes/sync.py`

New FastAPI router mounted at `/rag/sync`.

```
POST /rag/sync
Headers:
  X-Hub-Signature-256: sha256=<hmac-sha256 of raw request body using GITHUB_WEBHOOK_SECRET>
  Content-Type: application/json
Body: arbitrary JSON (body is verified but not parsed — sync always does a full scan)

Responses:
  202 Accepted      { "status": "sync started" }       (sync running in background)
  401 Unauthorized  { "detail": "Invalid signature" }
  500 Internal Error { "detail": "Webhook secret not configured" }
```

**Security:** Signature verification must use `hmac.compare_digest(computed_sig, provided_sig)` — never plain `==` — to prevent timing attacks. If `GITHUB_WEBHOOK_SECRET` is not set at startup, the endpoint rejects all requests with 500.

**Async behaviour:** Sync is dispatched as a FastAPI `BackgroundTask` and the endpoint returns 202 immediately. This prevents blocking the single Uvicorn worker during long embedding API calls (a sync of 10 PDFs can take 30–120 seconds). Sync results are logged server-side; the caller does not receive a result body.

---

### CLI: `lawrag sync`

New subcommand added to `lawrag/cli/main.py`.

```
lawrag sync [--laws-dir PATH] [--force] [-v]

Options:
  --laws-dir PATH   Directory to scan for PDFs (default: LAWRAG_LAWS_DIR or ./data/laws)
  --force           Re-ingest all PDFs regardless of hash match
  -v, --verbose     Print per-file progress and SyncResult summary
```

New config function: `get_laws_dir() -> str` in `lawrag/config.py`, reads `LAWRAG_LAWS_DIR` env var (default `"./data/laws"`, consistent with other config defaults). If the resolved directory does not exist at scan time, `LocalPDFScanner.list_pdfs()` raises `FileNotFoundError` with a clear message rather than returning an empty list silently.

---

### GitHub Actions: `.github/workflows/sync-laws.yml`

GitHub Actions is not a GitHub webhook — it is a CI job that manually calls the endpoint. The workflow computes the HMAC over a fixed empty-string body and sends it in the `X-Hub-Signature-256` header. The endpoint verifies using the same body.

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
      - name: Trigger sync endpoint
        env:
          DEPLOY_URL: ${{ secrets.DEPLOY_URL }}
          WEBHOOK_SECRET: ${{ secrets.GITHUB_WEBHOOK_SECRET }}
        run: |
          BODY='{}'
          SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')"
          curl -f -X POST "$DEPLOY_URL/rag/sync" \
            -H "Content-Type: application/json" \
            -H "X-Hub-Signature-256: $SIG" \
            -d "$BODY"
```

The server-side handler must read the raw request body bytes and compute HMAC over exactly those bytes using `GITHUB_WEBHOOK_SECRET`, then compare with `hmac.compare_digest`. Since the Actions workflow always sends `'{}'` as the body, the server will compute HMAC over `b'{}'`. Both sides must agree on this literal body — if any future caller sends a different body, the HMAC will not match.

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
POST /rag/sync  (HMAC-SHA256 over body)
        │
   Verify signature (hmac.compare_digest)
        │
   Return 202 immediately
   BackgroundTask: SyncManager.run()
        │
   LocalPDFScanner.list_pdfs()
   → PDFEntry(path, law_name, content_hash) per file
        │
   For each PDFEntry:
     get_index_metadata(law_name) → stored content_hash
     content_hash differs or None? ──yes──► Ingestor.ingest(path, content_hash=hash)
                                   ──no───► skip
        │
   Log SyncResult { ingested, skipped, errors }
```

---

## Required Change to Existing Code

`Ingestor.ingest()` in `packages/rag/src/lawrag/pipeline/ingestor.py` must gain a new optional parameter:

```python
def ingest(
    self,
    pdf_path: str | Path,
    law_name: Optional[str] = None,
    last_modified: Optional[str] = None,
    content_hash: Optional[str] = None,   # NEW: provided by SyncManager
    verbose: bool = False,
    law_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> List[Chunk]:
```

When `content_hash` is provided, it is forwarded to `_embed_and_store()` instead of `None`. This is backward-compatible — all existing callers continue to work.

---

## Future: Git LFS Migration Path

When the number or size of PDFs warrants LFS:

1. Run `git lfs track "data/laws/*.pdf"` and commit `.gitattributes`.
2. On the server, run `git lfs pull` before sync to materialise PDF files locally.
3. `LocalPDFScanner` continues to work unchanged — it reads local files regardless of whether they came from LFS or plain git.
4. No code changes to `SyncManager` or any other component.

**Constraint:** This migration path requires PDFs to be materialised on disk (via `git lfs pull`). A non-checkout LFS variant (where the server never stores full binaries) would require a different `PDFSource` implementation with download-and-cleanup semantics — that is out of scope for this spec.

---

## Testing

| Test | Approach |
|---|---|
| `LocalPDFScanner` | Create temp dir with sample PDFs; assert `PDFEntry` list and SHA256 values |
| `LocalPDFScanner` law name derivation | File `建築法_v2.pdf` → `law_name == "建築法"` (suffix stripped) |
| `LocalPDFScanner` missing directory | Non-existent path → `FileNotFoundError` with message |
| `Ingestor.ingest` content_hash forwarding | Call `ingest(pdf_path, content_hash="abc123")`; assert ChromaDB index stores `"abc123"` |
| `SyncManager` skip | Mock store returning matching hash; assert no `Ingestor.ingest` calls |
| `SyncManager` ingest | Mock store returning different hash; assert `Ingestor.ingest` called with correct `content_hash` |
| `SyncManager` skip on second run | Run `SyncManager.run()` twice without changing files; assert second run skips all |
| `SyncManager` error handling | Mock `Ingestor.ingest` raising exception for one PDF; assert others still processed |
| `/rag/sync` valid signature | Correct HMAC over `b'{}'` → 202 |
| `/rag/sync` invalid signature | Wrong HMAC → 401 |
| `/rag/sync` no secret configured | Missing env var → 500 |
| `/rag/sync` returns immediately | Endpoint returns before sync completes (background task) |
