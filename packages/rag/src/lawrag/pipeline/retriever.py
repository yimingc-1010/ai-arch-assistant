"""Retriever pipeline: query → embedding → ChromaDB → LLM → answer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from lawrag.store.chroma import LawChromaStore
from lawrag.providers.base import EmbeddingProvider, LLMProvider

_SYSTEM_PROMPT = """你是一位專業的法律助理，專門解答關於中華民國法規的問題。
請根據以下提供的法條內容盡量完整地回答問題。
- 請善用所有提供的法條，即使不是完全符合，也請引用相關法條加以說明
- 回答時請引用相關法條（例如：依建築法第30條）
- 如果法條只能部分回答問題，請先回答能回答的部分，再指出尚需釐清之處
- 僅在提供的法條中完全沒有任何相關內容時，才說明找不到相關規定
- 請使用繁體中文回答"""

_CHECKLIST_SYSTEM_PROMPT = """你是一位專業的建築法規合規顧問。
請根據以下法條，以 Markdown 核取清單格式（- [ ] 項目）回答問題。
每個項目須附上法條依據，格式：- [ ] 說明（依建築法第X條）
- 請善用所有提供的法條，即使不是完全符合，也請列入相關項目
- 如果法條只能部分回答，請先列出可確認的項目，再補充說明尚需釐清之處
- 僅在完全沒有任何相關法條時，才說明找不到相關規定
- 請以繁體中文回答，清單盡量精確具體、可操作。"""


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
    verification: Optional["VerificationResult"] = None  # type: ignore[name-defined]
    query_plan: Optional["QueryPlan"] = None  # type: ignore[name-defined]


def _build_context(results: List[dict]) -> str:
    """Build a formatted context string from retrieved chunks."""
    parts: List[str] = []
    for r in results:
        article = r.get("article_number", "")
        chapter = r.get("chapter", "")
        header = f"【{r['law_name']}】"
        if chapter:
            header += f" {chapter}"
        if article:
            header += f" {article}"
        parts.append(f"{header}\n{r['text']}")
    return "\n\n---\n\n".join(parts)


def _build_sources(results: List[dict]) -> List[Source]:
    return [
        Source(
            law_name=r.get("law_name", ""),
            article_number=r.get("article_number", ""),
            chapter=r.get("chapter", ""),
            text=r.get("text", ""),
            score=float(r.get("score", 0.0)),
            page=int(r.get("page_start", 1)),
        )
        for r in results
    ]


def _dedup_results(results: List[dict]) -> List[dict]:
    """Deduplicate results by chunk_id, keeping the lowest score (most similar)."""
    seen: dict[str, dict] = {}
    for r in results:
        cid = r["chunk_id"]
        if cid not in seen or r["score"] < seen[cid]["score"]:
            seen[cid] = r
    return list(seen.values())


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
        output_format: Literal["prose", "checklist"] = "prose",
        verify_citations: bool = False,
        jurisdictions: Optional[List[str]] = None,
        law_types: Optional[List[str]] = None,
    ) -> RAGResponse:
        """Answer a legal question using retrieved law article chunks.

        Args:
            question:        User's question (繁體中文 or mixed).
            law_names:       Restrict retrieval to these laws. None → all ingested.
            n_results:       Number of chunks to retrieve.
            include_sources: Whether to populate the sources list in the response.
            output_format:   "prose" (default) or "checklist" (Markdown checkbox list).
            verify_citations: Whether to run CitationVerifier on the answer.
            jurisdictions:   Filter retrieved chunks to these jurisdictions.
            law_types:       Filter retrieved chunks to these law hierarchy types.

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
            jurisdictions=jurisdictions,
            law_types=law_types,
        )

        # 3. Build context and generate answer
        context = _build_context(results)
        system = _CHECKLIST_SYSTEM_PROMPT if output_format == "checklist" else _SYSTEM_PROMPT
        user_message = f"以下是相關法條內容：\n\n{context}\n\n---\n\n問題：{question}"
        answer = self._llm.complete(system=system, user=user_message)

        # 4. Build sources
        sources = _build_sources(results) if include_sources else []

        # 5. Optional citation verification
        verification = None
        if verify_citations and include_sources:
            from lawrag.pipeline.verifier import CitationVerifier
            verification = CitationVerifier().verify(answer, sources)

        return RAGResponse(
            answer=answer,
            sources=sources,
            llm_provider=self._llm.provider_name,
            model=self._llm.model_name,
            retrieved_chunk_count=len(results),
            verification=verification,
        )


class AgentRetriever:
    """Multi-step agentic RAG: plan → multi-query → deduplicate → answer → (verify).

    Usage::

        from lawrag.pipeline.planner import QueryPlanner
        planner = QueryPlanner(llm=llm)
        retriever = AgentRetriever(store=store, embedder=embedder, llm=llm, planner=planner)
        response = retriever.query("我在台北市頂樓加蓋需要注意哪些法規？")
    """

    def __init__(
        self,
        store: LawChromaStore,
        embedder: EmbeddingProvider,
        llm: LLMProvider,
        planner: "QueryPlanner",  # type: ignore[name-defined]
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._llm = llm
        self._planner = planner

    def query(
        self,
        question: str,
        law_names: Optional[List[str]] = None,
        n_results: int = 5,
        include_sources: bool = True,
        output_format: Literal["prose", "checklist"] = "prose",
        verify_citations: bool = False,
    ) -> RAGResponse:
        """Agentic RAG query with automatic planning and multi-step retrieval.

        Args:
            question:         User's question.
            law_names:        Optional law name filter (overrides planner jurisdiction logic).
            n_results:        Total number of chunks to surface after deduplication.
            include_sources:  Whether to populate sources in the response.
            output_format:    "prose" or "checklist".
            verify_citations: Whether to run CitationVerifier on the answer.

        Returns:
            RAGResponse enriched with query_plan metadata.
        """
        from lawrag.pipeline.planner import QueryPlanner  # noqa: F401 (type check)

        # Step 1: Plan
        available_laws = law_names if law_names is not None else self._store.list_law_names()
        plan = self._planner.plan(question, available_laws)

        # Step 2: Multi-step retrieval — one embed+query per sub-query
        all_results: List[dict] = []
        per_query_k = max(n_results, 3)  # retrieve at least 3 per sub-query

        for sub_q in plan.sub_queries:
            vec = self._embedder.embed([sub_q], input_type="query")[0]
            results = self._store.query(
                query_vector=vec,
                law_names=law_names,
                n_results=per_query_k,
                jurisdictions=plan.required_jurisdictions,
                law_types=plan.required_law_types,
            )
            all_results.extend(results)

        # Step 3: Deduplicate and keep top-k
        deduped = _dedup_results(all_results)
        deduped.sort(key=lambda x: x["score"])
        top_results = deduped[:n_results]

        # Step 4: Generate answer
        context = _build_context(top_results)
        system = _CHECKLIST_SYSTEM_PROMPT if output_format == "checklist" else _SYSTEM_PROMPT
        user_message = f"以下是相關法條內容：\n\n{context}\n\n---\n\n問題：{question}"
        answer = self._llm.complete(system=system, user=user_message)

        # Step 5: Build sources
        sources = _build_sources(top_results) if include_sources else []

        # Step 6: Optional citation verification
        verification = None
        if verify_citations and include_sources:
            from lawrag.pipeline.verifier import CitationVerifier
            verification = CitationVerifier().verify(answer, sources)

        return RAGResponse(
            answer=answer,
            sources=sources,
            llm_provider=self._llm.provider_name,
            model=self._llm.model_name,
            retrieved_chunk_count=len(top_results),
            verification=verification,
            query_plan=plan,
        )
