"""Unit tests for the Retriever pipeline (all external deps mocked)."""

from unittest.mock import MagicMock
import pytest

from lawrag.pipeline.retriever import Retriever, RAGResponse, Source


def _make_store_results(n: int = 3) -> list[dict]:
    return [
        {
            "chunk_id": f"chunk_{i}",
            "text": f"第{i}條 本條文內容說明{i}。",
            "score": 0.1 * i,
            "law_name": "建築法",
            "article_number": f"第{i}條",
            "chapter": "第一章 總則",
            "char_count": 20,
            "strategy": "article",
            "page_start": i,
            "page_end": i,
            "embedding_model": "voyage",
            "ingested_at": "2024-01-01T00:00:00Z",
        }
        for i in range(1, n + 1)
    ]


class TestRetriever:
    def _make_retriever(self, store_results=None):
        store = MagicMock()
        store.query.return_value = _make_store_results() if store_results is None else store_results

        embedder = MagicMock()
        embedder.embed.return_value = [[0.1] * 8]
        embedder.provider_name = "voyage"

        llm = MagicMock()
        llm.complete.return_value = "依建築法第1條，申請建造執照需備齊文件。"
        llm.provider_name = "anthropic"
        llm.model_name = "claude-sonnet-4-6"

        retriever = Retriever(store=store, embedder=embedder, llm=llm)
        return retriever, store, embedder, llm

    def test_query_returns_ragresponse(self):
        retriever, _, _, _ = self._make_retriever()
        response = retriever.query("申請建造執照需要哪些文件？")

        assert isinstance(response, RAGResponse)
        assert response.answer
        assert response.llm_provider == "anthropic"
        assert response.model == "claude-sonnet-4-6"

    def test_query_embeds_with_query_input_type(self):
        retriever, _, embedder, _ = self._make_retriever()
        retriever.query("測試問題")

        embedder.embed.assert_called_once()
        call_kwargs = embedder.embed.call_args
        assert call_kwargs[1].get("input_type") == "query" or \
               (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "query")

    def test_query_passes_law_names_to_store(self):
        retriever, store, _, _ = self._make_retriever()
        retriever.query("問題", law_names=["建築法"])

        store.query.assert_called_once()
        kwargs = store.query.call_args[1]
        assert kwargs["law_names"] == ["建築法"]

    def test_query_sources_populated(self):
        retriever, _, _, _ = self._make_retriever(_make_store_results(3))
        response = retriever.query("問題", include_sources=True)

        assert len(response.sources) == 3
        assert all(isinstance(s, Source) for s in response.sources)

    def test_query_sources_excluded(self):
        retriever, _, _, _ = self._make_retriever()
        response = retriever.query("問題", include_sources=False)

        assert response.sources == []

    def test_query_no_results(self):
        retriever, _, _, llm = self._make_retriever(store_results=[])
        response = retriever.query("問題")

        assert response.retrieved_chunk_count == 0
        llm.complete.assert_called_once()  # LLM still called (with empty context)

    def test_llm_receives_context(self):
        retriever, _, _, llm = self._make_retriever(_make_store_results(2))
        retriever.query("申請建造執照需要哪些文件？")

        call_args = llm.complete.call_args
        user_msg = call_args[1].get("user") or call_args[0][1]
        assert "建築法" in user_msg
        assert "申請建造執照需要哪些文件？" in user_msg
