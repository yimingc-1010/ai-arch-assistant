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
