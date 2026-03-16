# GitHub PDF Source Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub repository (`data/laws/`) as the authoritative source for law PDFs, with content-hash-based change detection and three sync trigger modes (CLI, scheduled, webhook).

**Architecture:** A new `lawrag.sync` module provides `LocalPDFScanner` (detects changed PDFs via SHA256) and `SyncManager` (coordinates scan → diff → ingest). The existing `Ingestor.ingest()` is extended with a `content_hash` parameter so hashes survive to the index. A new `POST /rag/sync` FastAPI endpoint accepts HMAC-signed requests and dispatches sync as a background task.

**Tech Stack:** Python 3.10+, FastAPI BackgroundTasks, `hmac` stdlib, `hashlib` stdlib, pytest with unittest.mock, GitHub Actions.

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Modify | `packages/rag/src/lawrag/pipeline/ingestor.py` | Add `content_hash` param to `ingest()`, thread it to `_embed_and_store()` |
| Modify | `packages/rag/src/lawrag/config.py` | Add `get_laws_dir()` reading `LAWRAG_LAWS_DIR` |
| Create | `packages/rag/src/lawrag/sync/__init__.py` | Re-export `LocalPDFScanner`, `SyncManager`, `SyncResult` |
| Create | `packages/rag/src/lawrag/sync/scanner.py` | `PDFEntry` dataclass, `PDFSource` protocol, `LocalPDFScanner` |
| Create | `packages/rag/src/lawrag/sync/manager.py` | `SyncResult` dataclass, `SyncManager` class |
| Modify | `packages/rag/src/lawrag/cli/main.py` | Add `lawrag sync` subcommand |
| Create | `packages/api/src/autocrawler_api/routes/sync.py` | `POST /rag/sync` endpoint with HMAC auth + BackgroundTask |
| Modify | `packages/api/src/autocrawler_api/app.py` | Register sync router (same optional import pattern as rag) |
| Create | `data/laws/.gitkeep` | Create the PDF source directory under version control |
| Create | `.github/workflows/sync-laws.yml` | Push + schedule trigger for sync |
| Modify | `packages/rag/tests/test_ingestor.py` | Add test: `content_hash` forwarded when passed to `ingest()` |
| Create | `packages/rag/tests/test_scanner.py` | Tests for `LocalPDFScanner` |
| Create | `packages/rag/tests/test_sync_manager.py` | Tests for `SyncManager` |
| Create | `packages/api/tests/__init__.py` | Make tests a package |
| Create | `packages/api/tests/test_sync_route.py` | Tests for `POST /rag/sync` |

---

## Chunk 1: Ingestor Extension + Scanner

### Task 1: Extend `Ingestor.ingest()` to accept and forward `content_hash`

**Files:**
- Modify: `packages/rag/src/lawrag/pipeline/ingestor.py`
- Modify: `packages/rag/tests/test_ingestor.py`

- [ ] **Step 1: Write the failing test**

Add this test to `packages/rag/tests/test_ingestor.py` inside `class TestIngestor`:

```python
def test_ingest_forwards_content_hash_to_store(self, tmp_path):
    """When content_hash is passed to ingest(), it must reach upsert_chunks()."""
    pdf_file = tmp_path / "建築法.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")

    mock_chunks = [_make_chunk("建築法", 0)]

    with (
        patch("lawrag.pipeline.ingestor.extract_text", return_value=("content", {0: 1})),
        patch("lawrag.pipeline.ingestor.chunk_document", return_value=mock_chunks),
    ):
        store = MagicMock()
        embedder = MagicMock()
        embedder.embed.return_value = [[0.1] * 8]
        embedder.provider_name = "mock"

        ingestor = self._make_ingestor(store=store, embedder=embedder)
        ingestor.ingest(pdf_file, law_name="建築法", content_hash="abc123def456")

    call_kwargs = store.upsert_chunks.call_args[1]
    assert call_kwargs["content_hash"] == "abc123def456"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/yimingchen/Desktop/ai-arch-assistant
pytest packages/rag/tests/test_ingestor.py::TestIngestor::test_ingest_forwards_content_hash_to_store -v
```

Expected: FAIL (no `content_hash` parameter on `ingest()`)

- [ ] **Step 3: Extend `Ingestor.ingest()` signature and body**

In `packages/rag/src/lawrag/pipeline/ingestor.py`, update `ingest()`:

```python
def ingest(
    self,
    pdf_path: str | Path,
    law_name: Optional[str] = None,
    last_modified: Optional[str] = None,
    content_hash: Optional[str] = None,
    verbose: bool = False,
    law_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> List[Chunk]:
```

Also replace the `_embed_and_store` call at the bottom of `ingest()` (lines 113–121) so it uses the caller-supplied `content_hash` instead of the hardcoded `None`:

```python
return self._embed_and_store(
    chunks=chunks,
    last_modified=last_modified,
    content_hash=content_hash,          # was: None
    last_modified_source="page" if last_modified else "unknown",
    verbose=verbose,
)
```

- [ ] **Step 4: Run all ingestor tests to confirm nothing regressed**

```bash
pytest packages/rag/tests/test_ingestor.py -v
```

Expected: All tests PASS (backward-compatible — existing callers pass `content_hash=None` implicitly)

- [ ] **Step 5: Commit**

```bash
git add packages/rag/src/lawrag/pipeline/ingestor.py packages/rag/tests/test_ingestor.py
git commit -m "feat: add content_hash param to Ingestor.ingest() for sync change detection"
```

---

### Task 2: Add `get_laws_dir()` to config

**Files:**
- Modify: `packages/rag/src/lawrag/config.py`
- Create/Modify: `packages/rag/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Check if `packages/rag/tests/test_config.py` exists; if not, create it. Add:

```python
"""Tests for lawrag.config helper functions."""

import os
import pytest


def test_get_laws_dir_default(monkeypatch):
    monkeypatch.delenv("LAWRAG_LAWS_DIR", raising=False)
    from lawrag.config import get_laws_dir
    assert get_laws_dir() == "./data/laws"


def test_get_laws_dir_reads_env(monkeypatch):
    monkeypatch.setenv("LAWRAG_LAWS_DIR", "/custom/laws")
    from lawrag.config import get_laws_dir
    assert get_laws_dir() == "/custom/laws"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/yimingchen/Desktop/ai-arch-assistant
pytest packages/rag/tests/test_config.py -v
```

Expected: FAIL (`get_laws_dir` not found)

- [ ] **Step 3: Add the config function**

Append to `packages/rag/src/lawrag/config.py`:

```python
def get_laws_dir() -> str:
    return os.environ.get("LAWRAG_LAWS_DIR", "./data/laws")
```

- [ ] **Step 4: Run tests**

```bash
pytest packages/rag/tests/test_config.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/rag/src/lawrag/config.py packages/rag/tests/test_config.py
git commit -m "feat: add get_laws_dir() config function (LAWRAG_LAWS_DIR env var)"
```

---

### Task 3: Create `lawrag/sync/scanner.py` with `LocalPDFScanner`

**Files:**
- Create: `packages/rag/src/lawrag/sync/__init__.py`
- Create: `packages/rag/src/lawrag/sync/scanner.py`
- Create: `packages/rag/tests/test_scanner.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/rag/tests/test_scanner.py`:

```python
"""Tests for lawrag.sync.scanner."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


class TestLocalPDFScanner:
    def _make_pdf(self, directory: Path, name: str, content: bytes = b"%PDF-1.4") -> Path:
        path = directory / name
        path.write_bytes(content)
        return path

    def test_lists_pdf_entries(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        self._make_pdf(tmp_path, "建築法.pdf", b"%PDF-1.4 content-a")
        self._make_pdf(tmp_path, "都市計畫法.pdf", b"%PDF-1.4 content-b")

        scanner = LocalPDFScanner(laws_dir=tmp_path)
        entries = scanner.list_pdfs()

        law_names = {e.law_name for e in entries}
        assert law_names == {"建築法", "都市計畫法"}
        assert all(e.path.suffix == ".pdf" for e in entries)
        assert all(len(e.content_hash) == 64 for e in entries)  # SHA256 hex = 64 chars

    def test_content_hash_is_sha256_of_file_bytes(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        content = b"%PDF-1.4 specific content"
        self._make_pdf(tmp_path, "建築法.pdf", content)
        expected_hash = hashlib.sha256(content).hexdigest()

        scanner = LocalPDFScanner(laws_dir=tmp_path)
        entries = scanner.list_pdfs()

        assert entries[0].content_hash == expected_hash

    def test_law_name_strips_version_suffix(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        self._make_pdf(tmp_path, "建築法_v2.pdf")
        self._make_pdf(tmp_path, "都市計畫法_20231201.pdf")
        self._make_pdf(tmp_path, "消防法_sample.pdf")

        scanner = LocalPDFScanner(laws_dir=tmp_path)
        entries = scanner.list_pdfs()

        names = {e.law_name for e in entries}
        assert names == {"建築法", "都市計畫法", "消防法"}

    def test_ignores_non_pdf_files(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        self._make_pdf(tmp_path, "建築法.pdf")
        (tmp_path / "readme.txt").write_text("ignore me")
        (tmp_path / "notes.docx").write_bytes(b"ignore")

        scanner = LocalPDFScanner(laws_dir=tmp_path)
        entries = scanner.list_pdfs()

        assert len(entries) == 1
        assert entries[0].law_name == "建築法"

    def test_raises_file_not_found_for_missing_directory(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        missing = tmp_path / "does_not_exist"
        scanner = LocalPDFScanner(laws_dir=missing)

        with pytest.raises(FileNotFoundError, match="does_not_exist"):
            scanner.list_pdfs()

    def test_local_pdf_scanner_satisfies_pdf_source_protocol(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner, PDFSource
        assert isinstance(LocalPDFScanner(tmp_path), PDFSource)

    def test_empty_directory_returns_empty_list(self, tmp_path):
        from lawrag.sync.scanner import LocalPDFScanner

        scanner = LocalPDFScanner(laws_dir=tmp_path)
        assert scanner.list_pdfs() == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest packages/rag/tests/test_scanner.py -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Create the sync package and scanner**

Create `packages/rag/src/lawrag/sync/__init__.py` (empty for now):

```python
```

Create `packages/rag/src/lawrag/sync/scanner.py`:

```python
"""PDF source abstraction for the sync pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, runtime_checkable

# Suffix-stripping regex — must match Ingestor._infer_law_name() exactly.
_SUFFIX_RE = re.compile(r"[_\-](sample|v\d+|\d{6,8})$", re.IGNORECASE)


@dataclass
class PDFEntry:
    """A discovered PDF file with pre-computed metadata."""

    path: Path
    law_name: str      # Derived from filename stem (version suffixes stripped)
    content_hash: str  # SHA256 hex digest of raw file bytes


@runtime_checkable  # enables isinstance() checks in tests
class PDFSource(Protocol):
    """Protocol for PDF source implementations (local dir, LFS, etc.)."""

    def list_pdfs(self) -> List[PDFEntry]: ...


class LocalPDFScanner:
    """Scans a local directory for *.pdf files and returns PDFEntry objects.

    Raises FileNotFoundError if the directory does not exist at scan time.
    """

    def __init__(self, laws_dir: Path) -> None:
        self._laws_dir = Path(laws_dir)

    def list_pdfs(self) -> List[PDFEntry]:
        if not self._laws_dir.exists():
            raise FileNotFoundError(
                f"Laws directory not found: {self._laws_dir}. "
                f"Create the directory or set LAWRAG_LAWS_DIR to an existing path."
            )

        entries: List[PDFEntry] = []
        for pdf_path in sorted(self._laws_dir.glob("*.pdf")):
            law_name = _SUFFIX_RE.sub("", pdf_path.stem)
            raw = pdf_path.read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
            entries.append(PDFEntry(path=pdf_path, law_name=law_name, content_hash=content_hash))

        return entries
```

- [ ] **Step 4: Run tests**

```bash
pytest packages/rag/tests/test_scanner.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/rag/src/lawrag/sync/ packages/rag/tests/test_scanner.py
git commit -m "feat: add lawrag.sync.scanner with LocalPDFScanner and PDFSource protocol"
```

---

## Chunk 2: SyncManager + CLI

### Task 4: Create `SyncManager`

**Files:**
- Create: `packages/rag/src/lawrag/sync/manager.py`
- Modify: `packages/rag/src/lawrag/sync/__init__.py`
- Create: `packages/rag/tests/test_sync_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/rag/tests/test_sync_manager.py`:

```python
"""Tests for lawrag.sync.manager.SyncManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_scanner(entries):
    """Return a mock PDFSource that yields the given PDFEntry list."""
    from lawrag.sync.scanner import PDFEntry
    scanner = MagicMock()
    scanner.list_pdfs.return_value = [
        PDFEntry(path=Path(f"/laws/{name}.pdf"), law_name=name, content_hash=ch)
        for name, ch in entries
    ]
    return scanner


class TestSyncManager:
    def _make_manager(self, scanner, store=None, embedder=None):
        from lawrag.sync.manager import SyncManager
        store = store or MagicMock()
        embedder = embedder or MagicMock()
        embedder.provider_name = "mock"
        return SyncManager(source=scanner, store=store, embedder=embedder)

    # ------------------------------------------------------------------
    # Skip logic
    # ------------------------------------------------------------------

    def test_skips_when_hash_matches(self):
        scanner = _make_scanner([("建築法", "aabbcc")])
        store = MagicMock()
        store.get_index_metadata.return_value = {"content_hash": "aabbcc"}

        manager = self._make_manager(scanner, store=store)

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            result = manager.run()

        MockIngestor.return_value.ingest.assert_not_called()
        assert result.skipped == ["建築法"]
        assert result.ingested == []
        assert result.errors == []

    def test_ingests_when_hash_differs(self):
        scanner = _make_scanner([("建築法", "newhash")])
        store = MagicMock()
        store.get_index_metadata.return_value = {"content_hash": "oldhash"}

        manager = self._make_manager(scanner, store=store)

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.return_value = []
            result = manager.run()

        MockIngestor.return_value.ingest.assert_called_once_with(
            Path("/laws/建築法.pdf"),
            law_name="建築法",
            content_hash="newhash",
        )
        assert result.ingested == ["建築法"]
        assert result.skipped == []

    def test_ingests_when_stored_hash_is_none(self):
        """First sync after manual `lawrag ingest` — stored hash is None."""
        scanner = _make_scanner([("建築法", "newhash")])
        store = MagicMock()
        store.get_index_metadata.return_value = {"content_hash": None}

        manager = self._make_manager(scanner, store=store)

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.return_value = []
            result = manager.run()

        MockIngestor.return_value.ingest.assert_called_once()
        assert result.ingested == ["建築法"]

    def test_ingests_when_no_index_entry(self):
        """Brand new law — not yet in ChromaDB."""
        scanner = _make_scanner([("建築法", "newhash")])
        store = MagicMock()
        store.get_index_metadata.return_value = None

        manager = self._make_manager(scanner, store=store)

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.return_value = []
            result = manager.run()

        MockIngestor.return_value.ingest.assert_called_once()
        assert result.ingested == ["建築法"]

    # ------------------------------------------------------------------
    # Force flag
    # ------------------------------------------------------------------

    def test_force_re_ingests_even_when_hash_matches(self):
        scanner = _make_scanner([("建築法", "samehash")])
        store = MagicMock()
        store.get_index_metadata.return_value = {"content_hash": "samehash"}

        manager = self._make_manager(scanner, store=store)

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.return_value = []
            result = manager.run(force=True)

        MockIngestor.return_value.ingest.assert_called_once()
        assert result.ingested == ["建築法"]

    # ------------------------------------------------------------------
    # Error isolation
    # ------------------------------------------------------------------

    def test_scan_error_is_isolated_and_returned_in_errors(self):
        """If list_pdfs() raises, run() returns a SyncResult with the error."""
        scanner = MagicMock()
        scanner.list_pdfs.side_effect = FileNotFoundError("missing dir")

        manager = self._make_manager(scanner)
        result = manager.run()

        assert result.ingested == []
        assert result.skipped == []
        assert any("scan:" in e for e in result.errors)

    def test_error_in_one_pdf_does_not_stop_others(self):
        scanner = _make_scanner([("建築法", "hash1"), ("消防法", "hash2")])
        store = MagicMock()
        store.get_index_metadata.return_value = None  # both new

        manager = self._make_manager(scanner, store=store)

        def _ingest_side_effect(path, law_name, content_hash):
            if law_name == "建築法":
                raise RuntimeError("embedding API error")
            return []

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.side_effect = _ingest_side_effect
            result = manager.run()

        assert "消防法" in result.ingested
        assert any("建築法" in e for e in result.errors)

    # ------------------------------------------------------------------
    # Second-run idempotency regression test
    # ------------------------------------------------------------------

    def test_second_run_skips_all_when_no_files_changed(self, tmp_path):
        """After a full sync, a second run with no file changes must skip everything."""
        from lawrag.sync.scanner import LocalPDFScanner, PDFEntry
        from lawrag.sync.manager import SyncManager
        from lawrag.pdf.chunker import Chunk
        import hashlib

        # Create two real PDFs in a temp dir
        content_a = b"%PDF-1.4 law-a"
        content_b = b"%PDF-1.4 law-b"
        (tmp_path / "建築法.pdf").write_bytes(content_a)
        (tmp_path / "消防法.pdf").write_bytes(content_b)

        hash_a = hashlib.sha256(content_a).hexdigest()
        hash_b = hashlib.sha256(content_b).hexdigest()

        # Store that simulates: first call returns None (no entry), subsequent calls
        # return the stored hash (as if first sync saved it).
        call_counts: dict = {}

        def _get_metadata(law_name):
            count = call_counts.get(law_name, 0)
            call_counts[law_name] = count + 1
            if count == 0:
                return None  # first run: not yet ingested
            # second run: return the hash that was "stored" by the first ingest
            return {"content_hash": hash_a if law_name == "建築法" else hash_b}

        store = MagicMock()
        store.get_index_metadata.side_effect = _get_metadata

        embedder = MagicMock()
        embedder.embed.return_value = [[0.1] * 8]
        embedder.provider_name = "mock"

        scanner = LocalPDFScanner(laws_dir=tmp_path)

        dummy_chunk = Chunk(
            chunk_id="x", law_name="x", source_file="x", article_number="",
            chapter="", text="x", char_count=1, strategy="article",
            page_start=1, page_end=1,
        )

        with patch("lawrag.sync.manager.Ingestor") as MockIngestor:
            MockIngestor.return_value.ingest.return_value = [dummy_chunk]

            manager = SyncManager(source=scanner, store=store, embedder=embedder)
            first = manager.run()
            second = manager.run()

        assert set(first.ingested) == {"建築法", "消防法"}
        assert second.ingested == []
        assert set(second.skipped) == {"建築法", "消防法"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest packages/rag/tests/test_sync_manager.py -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Create `manager.py`**

Create `packages/rag/src/lawrag/sync/manager.py`:

```python
"""SyncManager: orchestrates scan → diff → ingest pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lawrag.sync.scanner import PDFSource
    from lawrag.store.chroma import LawChromaStore
    from lawrag.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    ingested: list = field(default_factory=list)  # law names successfully ingested
    skipped: list = field(default_factory=list)   # unchanged, skipped
    errors: list = field(default_factory=list)    # "law_name: error message" strings


class SyncManager:
    """Coordinates the full sync flow: scan → compare hashes → ingest changed PDFs."""

    def __init__(
        self,
        source: "PDFSource",
        store: "LawChromaStore",
        embedder: "EmbeddingProvider",
    ) -> None:
        self._source = source
        self._store = store
        self._embedder = embedder

    def run(self, force: bool = False, verbose: bool = False) -> SyncResult:
        """Run the sync pipeline.

        Args:
            force:   Re-ingest all PDFs regardless of hash match.
            verbose: Log per-file progress.

        Returns:
            SyncResult with ingested, skipped, and error lists.
        """
        from lawrag.pipeline.ingestor import Ingestor

        result = SyncResult()
        ingestor = Ingestor(store=self._store, embedder=self._embedder)

        try:
            entries = self._source.list_pdfs()
        except Exception as exc:
            result.errors.append(f"scan: {exc}")
            return result

        for entry in entries:
            try:
                meta = self._store.get_index_metadata(entry.law_name)
                stored_hash = meta.get("content_hash") if meta else None

                needs_ingest = force or stored_hash is None or stored_hash != entry.content_hash

                if not needs_ingest:
                    if verbose:
                        logger.info("[sync] skip %s (hash unchanged)", entry.law_name)
                    result.skipped.append(entry.law_name)
                    continue

                if verbose:
                    logger.info("[sync] ingesting %s …", entry.law_name)

                ingestor.ingest(
                    entry.path,
                    law_name=entry.law_name,
                    content_hash=entry.content_hash,
                )
                result.ingested.append(entry.law_name)

            except Exception as exc:
                msg = f"{entry.law_name}: {exc}"
                logger.error("[sync] error — %s", msg)
                result.errors.append(msg)

        return result
```

- [ ] **Step 4: Run tests**

```bash
pytest packages/rag/tests/test_sync_manager.py -v
```

Expected: All PASS

- [ ] **Step 5: Update `sync/__init__.py`**

Update `packages/rag/src/lawrag/sync/__init__.py`:

```python
"""lawrag.sync — PDF source scanning and sync management."""

from lawrag.sync.scanner import LocalPDFScanner, PDFEntry, PDFSource
from lawrag.sync.manager import SyncManager, SyncResult

__all__ = ["LocalPDFScanner", "PDFEntry", "PDFSource", "SyncManager", "SyncResult"]
```

- [ ] **Step 6: Commit**

```bash
git add packages/rag/src/lawrag/sync/ packages/rag/tests/test_sync_manager.py
git commit -m "feat: add SyncManager with hash-based change detection"
```

---

### Task 5: Add `lawrag sync` CLI subcommand

**Files:**
- Modify: `packages/rag/src/lawrag/cli/main.py`

- [ ] **Step 1: Add `cmd_sync` function and subparser**

In `packages/rag/src/lawrag/cli/main.py`, add the following function before `main()`:

```python
def cmd_sync(args: argparse.Namespace) -> int:
    from lawrag.providers import get_embedding_provider
    from lawrag.sync.scanner import LocalPDFScanner
    from lawrag.sync.manager import SyncManager
    from lawrag import config

    laws_dir = Path(args.laws_dir or config.get_laws_dir())
    store = _build_store(args.chroma_dir)
    embedder = get_embedding_provider(args.embedding_provider)

    scanner = LocalPDFScanner(laws_dir=laws_dir)
    manager = SyncManager(source=scanner, store=store, embedder=embedder)

    try:
        result = manager.run(force=args.force, verbose=args.verbose)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.verbose or result.errors:
        print(f"Ingested: {len(result.ingested)}  Skipped: {len(result.skipped)}  Errors: {len(result.errors)}")
        for law in result.ingested:
            print(f"  + {law}")
        for law in result.skipped:
            print(f"  = {law}")
        for err in result.errors:
            print(f"  ! {err}", file=sys.stderr)
    else:
        print(f"Sync complete: {len(result.ingested)} ingested, {len(result.skipped)} skipped")

    return 1 if result.errors else 0
```

Also add `Path` to the imports at the top if not present (it already is — `from pathlib import Path`).

Then add a subparser inside `main()`, after the `list_parser` block and before `args = parser.parse_args()`:

```python
# ── sync ────────────────────────────────────────────────────────────
sync_parser = subparsers.add_parser("sync", help="Sync PDFs from data/laws/ into the vector store")
sync_parser.add_argument(
    "--laws-dir",
    default=None,
    help="Directory to scan for PDFs (default: LAWRAG_LAWS_DIR or ./data/laws)",
)
sync_parser.add_argument(
    "--force",
    action="store_true",
    help="Re-ingest all PDFs regardless of hash match",
)
sync_parser.add_argument(
    "--embedding-provider",
    default=None,
    choices=["voyage", "openai"],
)
sync_parser.add_argument("-v", "--verbose", action="store_true")
sync_parser.add_argument("--chroma-dir", default=None)
```

And register the handler in `handlers`:

```python
handlers = {
    "ingest": cmd_ingest,
    "query": cmd_query,
    "list": cmd_list,
    "sync": cmd_sync,
}
```

- [ ] **Step 2: Verify the CLI registers the subcommand**

```bash
cd /Users/yimingchen/Desktop/ai-arch-assistant
lawrag sync --help
```

Expected: Help text for `lawrag sync` with `--laws-dir`, `--force`, `-v` options.

- [ ] **Step 3: Commit**

```bash
git add packages/rag/src/lawrag/cli/main.py
git commit -m "feat: add lawrag sync CLI subcommand"
```

---

## Chunk 3: API Webhook Endpoint

### Task 6: Create `POST /rag/sync` endpoint

**Files:**
- Create: `packages/api/src/autocrawler_api/routes/sync.py`
- Modify: `packages/api/src/autocrawler_api/app.py`
- Create: `packages/api/tests/__init__.py`
- Create: `packages/api/tests/test_sync_route.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/api/tests/__init__.py` (empty).

Create `packages/api/tests/test_sync_route.py`:

```python
"""Tests for POST /rag/sync webhook endpoint."""

from __future__ import annotations

import hashlib
import hmac
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


BODY = b"{}"
SECRET = "test-webhook-secret"


def _make_sig(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    # Provide stub lawrag env vars so the app imports cleanly
    monkeypatch.setenv("LAWRAG_CHROMA_DIR", "/tmp/test-chroma")
    monkeypatch.setenv("LAWRAG_LAWS_DIR", "/tmp/test-laws")
    from autocrawler_api.app import create_app
    return TestClient(create_app())


class TestSyncRoute:
    def test_valid_signature_returns_202(self, client):
        sig = _make_sig(BODY, SECRET)
        with patch("autocrawler_api.routes.sync._run_sync_background"):
            resp = client.post(
                "/rag/sync",
                content=BODY,
                headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            )
        assert resp.status_code == 202
        assert resp.json()["status"] == "sync started"

    def test_invalid_signature_returns_401(self, client):
        resp = client.post(
            "/rag/sync",
            content=BODY,
            headers={"X-Hub-Signature-256": "sha256=wronghex", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_header_returns_401(self, client):
        resp = client.post("/rag/sync", content=BODY)
        assert resp.status_code == 401

    def test_no_secret_configured_returns_500(self, monkeypatch):
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("LAWRAG_CHROMA_DIR", "/tmp/test-chroma")
        monkeypatch.setenv("LAWRAG_LAWS_DIR", "/tmp/test-laws")
        from autocrawler_api.app import create_app
        client = TestClient(create_app())
        resp = client.post(
            "/rag/sync",
            content=BODY,
            headers={"X-Hub-Signature-256": "sha256=anything"},
        )
        assert resp.status_code == 500

    def test_sync_dispatched_as_background_task(self, client):
        """Verify _run_sync_background is scheduled (not called inline before 202 returns).

        Note: FastAPI TestClient runs BackgroundTasks synchronously after the response,
        so we verify the function was called exactly once (i.e. it was registered and
        executed) and that the endpoint returned 202.
        """
        sig = _make_sig(BODY, SECRET)
        with patch("autocrawler_api.routes.sync._run_sync_background") as mock_sync:
            resp = client.post(
                "/rag/sync",
                content=BODY,
                headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            )
        assert resp.status_code == 202
        mock_sync.assert_called_once()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/yimingchen/Desktop/ai-arch-assistant
pytest packages/api/tests/test_sync_route.py -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Create `routes/sync.py`**

Create `packages/api/src/autocrawler_api/routes/sync.py`:

```python
"""POST /rag/sync — HMAC-authenticated sync trigger endpoint."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


def _get_webhook_secret() -> str:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    return secret


def _verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    """Return True iff the X-Hub-Signature-256 header matches HMAC-SHA256 of body."""
    if not header or not header.startswith("sha256="):
        return False
    provided = header[len("sha256="):]
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, provided)


def _run_sync_background() -> None:
    """Run the full sync pipeline. Called from a BackgroundTask."""
    try:
        from lawrag import config as lawrag_config
        from lawrag.store.chroma import LawChromaStore
        from lawrag.providers import get_embedding_provider
        from lawrag.sync.scanner import LocalPDFScanner
        from lawrag.sync.manager import SyncManager

        laws_dir = Path(lawrag_config.get_laws_dir())
        store = LawChromaStore(persist_dir=lawrag_config.get_chroma_dir())
        embedder = get_embedding_provider()
        scanner = LocalPDFScanner(laws_dir=laws_dir)
        manager = SyncManager(source=scanner, store=store, embedder=embedder)

        result = manager.run(verbose=True)
        logger.info(
            "[sync] complete — ingested=%d skipped=%d errors=%d",
            len(result.ingested), len(result.skipped), len(result.errors),
        )
        if result.errors:
            for err in result.errors:
                logger.error("[sync] error: %s", err)
    except Exception:
        logger.exception("[sync] unexpected error during background sync")


@router.post("/sync", summary="Trigger a law PDF sync (GitHub Actions webhook)")
async def sync_trigger(request: Request, background_tasks: BackgroundTasks):
    """Verify HMAC signature and dispatch sync as a background task.

    Accepts POST from GitHub Actions (or any caller) with:
      Header: X-Hub-Signature-256: sha256=<hmac-sha256 of body>
      Body:   {} (static JSON body; both caller and server agree on this)

    Returns 202 immediately; sync runs in the background.
    """
    secret = _get_webhook_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(body, sig_header, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    background_tasks.add_task(_run_sync_background)
    return {"status": "sync started"}
```

- [ ] **Step 4: Register the router in `app.py`**

In `packages/api/src/autocrawler_api/app.py`, add after the `rag` import block:

```python
    # lawrag sync route (optional — only registered when lawrag is installed)
    try:
        from autocrawler_api.routes import sync as sync_route
        app.include_router(sync_route.router)
    except ImportError:
        pass
```

- [ ] **Step 5: Run tests**

```bash
pytest packages/api/tests/test_sync_route.py -v
```

Expected: All PASS

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
pytest packages/rag/tests/ packages/api/tests/ -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add packages/api/src/autocrawler_api/routes/sync.py \
        packages/api/src/autocrawler_api/app.py \
        packages/api/tests/
git commit -m "feat: add POST /rag/sync webhook endpoint with HMAC auth and BackgroundTask"
```

---

## Chunk 4: Data Directory + GitHub Actions

### Task 7: Create `data/laws/` directory and GitHub Actions workflow

**Files:**
- Create: `data/laws/.gitkeep`
- Create: `.github/workflows/sync-laws.yml`

- [ ] **Step 1: Create the laws directory**

```bash
mkdir -p /Users/yimingchen/Desktop/ai-arch-assistant/data/laws
touch /Users/yimingchen/Desktop/ai-arch-assistant/data/laws/.gitkeep
```

- [ ] **Step 2: Create the GitHub Actions workflow**

Create `.github/workflows/sync-laws.yml`:

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

- [ ] **Step 3: Verify workflow YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/sync-laws.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

- [ ] **Step 4: Run full test suite one final time**

```bash
cd /Users/yimingchen/Desktop/ai-arch-assistant
pytest packages/rag/tests/ packages/api/tests/ -v
```

Expected: All PASS

- [ ] **Step 5: Final commit**

```bash
git add data/laws/.gitkeep .github/workflows/sync-laws.yml
git commit -m "feat: add data/laws/ PDF source directory and GitHub Actions sync workflow"
```

---

## Summary

After completing all tasks, the following will be in place:

| Feature | How to use |
|---|---|
| Add a law PDF | Copy to `data/laws/建築法.pdf`, commit, push |
| Manual sync | `lawrag sync -v` |
| Force re-ingest all | `lawrag sync --force` |
| Auto sync on push | Push to `data/laws/**` → GitHub Actions → `POST /rag/sync` |
| Daily sync | GitHub Actions cron at 02:00 UTC |

**GitHub Secrets to configure on the deployment repo:**
- `DEPLOY_URL` — e.g. `https://yourdomain.com`
- `GITHUB_WEBHOOK_SECRET` — any strong random string; also set as `GITHUB_WEBHOOK_SECRET` env var on the server
