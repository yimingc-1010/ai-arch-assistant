"""lawrag — Law regulation PDF RAG system.

Public API::

    from lawrag import Ingestor, Retriever, AgentRetriever, LawChromaStore

    store = LawChromaStore(persist_dir="./data/chroma")
    embedder = get_embedding_provider("voyage")
    llm = get_llm_provider("anthropic")

    ingestor = Ingestor(store=store, embedder=embedder)
    ingestor.ingest("建築法.pdf", verbose=True)

    retriever = Retriever(store=store, embedder=embedder, llm=llm)
    response = retriever.query("申請建造執照需要哪些文件？")
    print(response.answer)
"""

from lawrag.pipeline.ingestor import Ingestor
from lawrag.pipeline.retriever import Retriever, AgentRetriever, RAGResponse, Source
from lawrag.pipeline.planner import QueryPlanner, QueryPlan
from lawrag.pipeline.verifier import CitationVerifier, VerificationResult
from lawrag.store.chroma import LawChromaStore
from lawrag.providers import get_embedding_provider, get_llm_provider

__all__ = [
    "Ingestor",
    "Retriever",
    "AgentRetriever",
    "RAGResponse",
    "Source",
    "QueryPlanner",
    "QueryPlan",
    "CitationVerifier",
    "VerificationResult",
    "LawChromaStore",
    "get_embedding_provider",
    "get_llm_provider",
]

__version__ = "0.1.0"
