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
        from lawrag.sync.scanner import LocalPDFScanner
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
