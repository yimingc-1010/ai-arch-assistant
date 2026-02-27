"""Unit tests for LawChromaStore (ChromaDB mocked)."""

from unittest.mock import MagicMock, patch
import pytest

from lawrag.pdf.chunker import Chunk


def _make_chunk(law_name: str, article: str, text: str, idx: int = 0) -> Chunk:
    import hashlib
    key = f"{law_name}{article}{idx}"
    chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=chunk_id,
        law_name=law_name,
        source_file="test.pdf",
        article_number=article,
        chapter="第一章 總則",
        text=text,
        char_count=len(text),
        strategy="article",
        page_start=1,
        page_end=1,
    )


class TestLawChromaStore:
    """Tests that LawChromaStore calls ChromaDB correctly (all mocked)."""

    def _make_store(self, mock_client):
        """Patch chromadb.PersistentClient and return a LawChromaStore instance."""
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")
        return store, mock_index

    def test_upsert_chunks_calls_collection_upsert(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0

        # First call (index) → mock_index; second call (law collection) → mock_collection
        mock_client.get_or_create_collection.side_effect = [mock_index, mock_collection]

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        chunks = [_make_chunk("建築法", "第1條", "本法為建築法。", i) for i in range(3)]
        vectors = [[0.1] * 4] * 3

        store.upsert_chunks(chunks, vectors, embedding_model="voyage")

        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert len(call_kwargs["ids"]) == 3
        assert len(call_kwargs["embeddings"]) == 3
        assert len(call_kwargs["documents"]) == 3

    def test_upsert_chunks_stores_last_modified_in_chunk_metadata(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.side_effect = [mock_index, mock_collection]

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        chunks = [_make_chunk("建築法", "第1條", "本法為建築法。", 0)]
        vectors = [[0.1] * 4]

        store.upsert_chunks(
            chunks, vectors,
            embedding_model="voyage",
            last_modified="民國 111 年 05 月 11 日",
        )

        call_kwargs = mock_collection.upsert.call_args[1]
        meta = call_kwargs["metadatas"][0]
        assert meta["last_modified"] == "民國 111 年 05 月 11 日"

    def test_upsert_chunks_last_modified_none_stored_as_sentinel(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.side_effect = [mock_index, mock_collection]

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        chunks = [_make_chunk("建築法", "第1條", "本法為建築法。", 0)]
        vectors = [[0.1] * 4]

        store.upsert_chunks(chunks, vectors, embedding_model="voyage")  # no last_modified

        call_kwargs = mock_collection.upsert.call_args[1]
        meta = call_kwargs["metadatas"][0]
        # None is stored as empty string sentinel for ChromaDB compatibility
        assert meta["last_modified"] == ""

    def test_upsert_chunks_stores_content_hash_and_source_in_index(self):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.side_effect = [mock_index, mock_collection]

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        chunks = [_make_chunk("建築法", "第1條", "本法為建築法。", 0)]
        vectors = [[0.1] * 4]

        store.upsert_chunks(
            chunks, vectors,
            embedding_model="voyage",
            last_modified="民國 111 年 05 月 11 日",
            content_hash="abc123",
            last_modified_source="page",
        )

        index_upsert_kwargs = mock_index.upsert.call_args[1]
        index_meta = index_upsert_kwargs["metadatas"][0]
        assert index_meta["last_modified"] == "民國 111 年 05 月 11 日"
        assert index_meta["content_hash"] == "abc123"
        assert index_meta["last_modified_source"] == "page"

    def test_upsert_empty_chunks_is_noop(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        # Should not raise
        store.upsert_chunks([], [], embedding_model="voyage")

    def test_list_documents_empty(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        result = store.list_documents()
        assert result == []

    def test_list_documents_returns_metadata(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 1
        mock_index.get.return_value = {
            "metadatas": [{"law_name": "建築法", "chunk_count": 10, "ingested_at": "2024-01-01"}]
        }
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        result = store.list_documents()
        assert len(result) == 1
        assert result[0]["law_name"] == "建築法"

    def test_query_no_laws_returns_empty(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_index.get.return_value = {"metadatas": []}
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        results = store.query([0.1] * 4, law_names=[], n_results=5)
        assert results == []

    def test_get_index_metadata_returns_none_when_not_ingested(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 0
        mock_index.get.return_value = {"metadatas": []}
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        result = store.get_index_metadata("建築法")
        assert result is None

    def test_get_index_metadata_returns_dict_when_ingested(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 1
        mock_index.get.return_value = {
            "metadatas": [{
                "law_name": "建築法",
                "chunk_count": 5,
                "ingested_at": "2024-01-01T00:00:00+00:00",
                "last_modified": "民國 111 年 05 月 11 日",
                "content_hash": "abc123",
                "last_modified_source": "page",
            }]
        }
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        result = store.get_index_metadata("建築法")
        assert result is not None
        assert result["law_name"] == "建築法"
        assert result["last_modified"] == "民國 111 年 05 月 11 日"
        assert result["content_hash"] == "abc123"
        assert result["last_modified_source"] == "page"

    def test_get_index_metadata_normalises_sentinel_to_none(self):
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_index.count.return_value = 1
        mock_index.get.return_value = {
            "metadatas": [{
                "law_name": "建築法",
                "chunk_count": 3,
                "ingested_at": "2024-01-01T00:00:00+00:00",
                "last_modified": "",   # sentinel for None
                "content_hash": "",    # sentinel for None
                "last_modified_source": "unknown",
            }]
        }
        mock_client.get_or_create_collection.return_value = mock_index

        with patch("chromadb.PersistentClient", return_value=mock_client):
            from lawrag.store.chroma import LawChromaStore
            store = LawChromaStore(persist_dir="/tmp/test_chroma")

        result = store.get_index_metadata("建築法")
        assert result["last_modified"] is None
        assert result["content_hash"] is None
