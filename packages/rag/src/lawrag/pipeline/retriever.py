"""Retriever pipeline: query → embedding → ChromaDB → LLM → answer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from lawrag.store.chroma import LawChromaStore
from lawrag.providers.base import EmbeddingProvider, LLMProvider

_SYSTEM_PROMPT = """你是一位專業的法律助理，專門解答關於中華民國法規的問題。
請根據以下提供的法條內容來回答問題。
- 回答時請引用相關法條（例如：依建築法第30條）
- 如果提供的法條不足以回答問題，請明確說明
- 請使用繁體中文回答"""


@dataclass
class Source:
    law_name: str
    article_number: str
    chapter: str
    text: str
    score: float
    page: int


@dataclass
class RAGResponse:
    answer: str
    sources: List[Source]
    llm_provider: str
    model: str
    retrieved_chunk_count: int


class Retriever:
    """RAG pipeline that retrieves law chunks and generates an answer via LLM.

    Usage::

        retriever = Retriever(store=store, embedder=embedder, llm=llm)
        response = retriever.query("申請建造執照需要哪些文件？", law_names=["建築法"])
    """

    def __init__(
        self,
        store: LawChromaStore,
        embedder: EmbeddingProvider,
        llm: LLMProvider,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._llm = llm

    def query(
        self,
        question: str,
        law_names: Optional[List[str]] = None,
        n_results: int = 5,
        include_sources: bool = True,
    ) -> RAGResponse:
        """Answer a legal question using retrieved law article chunks.

        Args:
            question:        User's question (繁體中文 or mixed).
            law_names:       Restrict retrieval to these laws. None → all ingested.
            n_results:       Number of chunks to retrieve.
            include_sources: Whether to populate the sources list in the response.

        Returns:
            RAGResponse with the generated answer and retrieved sources.
        """
        # 1. Embed the query (asymmetric: input_type="query")
        query_vector = self._embedder.embed([question], input_type="query")[0]

        # 2. Retrieve relevant chunks
        results = self._store.query(
            query_vector=query_vector,
            law_names=law_names,
            n_results=n_results,
        )

        # 3. Build context for the LLM
        context_parts: List[str] = []
        for r in results:
            article = r.get("article_number", "")
            chapter = r.get("chapter", "")
            header = f"【{r['law_name']}】"
            if chapter:
                header += f" {chapter}"
            if article:
                header += f" {article}"
            context_parts.append(f"{header}\n{r['text']}")

        context = "\n\n---\n\n".join(context_parts)

        user_message = f"""以下是相關法條內容：

{context}

---

問題：{question}"""

        # 4. Generate answer
        answer = self._llm.complete(
            system=_SYSTEM_PROMPT,
            user=user_message,
        )

        # 5. Build source list
        sources: List[Source] = []
        if include_sources:
            for r in results:
                sources.append(
                    Source(
                        law_name=r.get("law_name", ""),
                        article_number=r.get("article_number", ""),
                        chapter=r.get("chapter", ""),
                        text=r.get("text", ""),
                        score=float(r.get("score", 0.0)),
                        page=int(r.get("page_start", 1)),
                    )
                )

        return RAGResponse(
            answer=answer,
            sources=sources,
            llm_provider=self._llm.provider_name,
            model=self._llm.model_name,
            retrieved_chunk_count=len(results),
        )
