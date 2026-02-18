"""Unit tests for the Ingestor pipeline (all external deps mocked)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lawrag.pdf.chunker import Chunk


def _make_chunk(law_name: str, idx: int) -> Chunk:
    import hashlib
    key = f"{law_name}article{idx}"
    chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=chunk_id,
        law_name=law_name,
        source_file="test.pdf",
        article_number=f"第{idx}條",
        chapter="",
        text=f"第{idx}條內容",
        char_count=10,
        strategy="article",
        page_start=1,
        page_end=1,
    )


class TestIngestor:
    def _make_ingestor(self, store=None, embedder=None):
        from lawrag.pipeline.ingestor import Ingestor
        store = store or MagicMock()
        embedder = embedder or MagicMock()
        embedder.provider_name = "mock"
        return Ingestor(store=store, embedder=embedder)

    def test_ingest_calls_extract_text(self, tmp_path):
        pdf_file = tmp_path / "建築法.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_chunks = [_make_chunk("建築法", i) for i in range(3)]
        mock_vectors = [[0.1] * 8] * 3

        with (
            patch("lawrag.pipeline.ingestor.extract_text", return_value=("text content", {0: 1})) as mock_extract,
            patch("lawrag.pipeline.ingestor.chunk_document", return_value=mock_chunks),
        ):
            store = MagicMock()
            embedder = MagicMock()
            embedder.embed.return_value = mock_vectors
            embedder.provider_name = "mock"

            ingestor = self._make_ingestor(store=store, embedder=embedder)
            chunks = ingestor.ingest(pdf_file)

        mock_extract.assert_called_once()
        assert len(chunks) == 3

    def test_ingest_upserts_to_store(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_chunks = [_make_chunk("建築法", i) for i in range(2)]
        mock_vectors = [[0.5] * 8] * 2

        with (
            patch("lawrag.pipeline.ingestor.extract_text", return_value=("content", {0: 1})),
            patch("lawrag.pipeline.ingestor.chunk_document", return_value=mock_chunks),
        ):
            store = MagicMock()
            embedder = MagicMock()
            embedder.embed.return_value = mock_vectors
            embedder.provider_name = "mock"

            ingestor = self._make_ingestor(store=store, embedder=embedder)
            ingestor.ingest(pdf_file, law_name="建築法")

        store.upsert_chunks.assert_called_once()
        call_args = store.upsert_chunks.call_args
        assert len(call_args[1]["chunks"]) == 2

    def test_ingest_empty_chunks_skips_upsert(self, tmp_path):
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with (
            patch("lawrag.pipeline.ingestor.extract_text", return_value=("", {0: 1})),
            patch("lawrag.pipeline.ingestor.chunk_document", return_value=[]),
        ):
            store = MagicMock()
            embedder = MagicMock()
            embedder.provider_name = "mock"

            ingestor = self._make_ingestor(store=store, embedder=embedder)
            chunks = ingestor.ingest(pdf_file)

        assert chunks == []
        store.upsert_chunks.assert_not_called()

    def test_law_name_inferred_from_filename(self, tmp_path):
        pdf_file = tmp_path / "建築法.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_chunks = [_make_chunk("建築法", 0)]

        with (
            patch("lawrag.pipeline.ingestor.extract_text", return_value=("content", {0: 1})),
            patch("lawrag.pipeline.ingestor.chunk_document", return_value=mock_chunks) as mock_chunk,
        ):
            store = MagicMock()
            embedder = MagicMock()
            embedder.embed.return_value = [[0.1] * 8]
            embedder.provider_name = "mock"

            ingestor = self._make_ingestor(store=store, embedder=embedder)
            ingestor.ingest(pdf_file)  # no law_name override

        # chunk_document should be called with inferred name "建築法"
        call_kwargs = mock_chunk.call_args[1]
        assert call_kwargs["law_name"] == "建築法"
