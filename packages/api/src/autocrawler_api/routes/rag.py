"""REST API routes for the lawrag RAG system."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Optional

try:
    from fastapi import APIRouter, File, Form, HTTPException, UploadFile
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError as e:
    raise ImportError("fastapi and pydantic are required") from e

try:
    from lawrag import Ingestor, Retriever, LawChromaStore
    from lawrag.providers import get_embedding_provider, get_llm_provider
    from lawrag import config as lawrag_config
    _LAWRAG_AVAILABLE = True
except ImportError:
    _LAWRAG_AVAILABLE = False


router = APIRouter(prefix="/rag", tags=["rag"])


def _require_lawrag() -> None:
    if not _LAWRAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="lawrag package is not installed. Run: pip install 'lawrag[all]'",
        )


def _get_store() -> "LawChromaStore":
    return LawChromaStore(persist_dir=lawrag_config.get_chroma_dir())


# ---------------------------------------------------------------------------
# POST /rag/ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", summary="Ingest a law PDF")
async def ingest_pdf(
    file: UploadFile = File(..., description="Law regulation PDF file"),
    law_name: Optional[str] = Form(None, description="Override law name (default: filename)"),
    embedding_provider: str = Form("voyage", description="voyage | openai"),
):
    """Upload a PDF file and ingest it into the vector store."""
    _require_lawrag()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        store = _get_store()
        embedder = get_embedding_provider(embedding_provider)
        ingestor = Ingestor(store=store, embedder=embedder)

        chunks = ingestor.ingest(
            pdf_path=tmp_path,
            law_name=law_name or Path(file.filename).stem,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "status": "ok",
        "law_name": law_name or Path(file.filename).stem,
        "chunk_count": len(chunks),
        "source_file": file.filename,
    }


# ---------------------------------------------------------------------------
# POST /rag/query
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    law_names: Optional[List[str]] = None
    n_results: int = 5
    llm_provider: str = "anthropic"
    embedding_provider: str = "voyage"
    include_sources: bool = True


@router.post("/query", summary="Ask a legal question")
def query_rag(req: QueryRequest):
    """Query the RAG system with a legal question.

    Returns the LLM-generated answer and the retrieved source chunks.
    """
    _require_lawrag()

    try:
        store = _get_store()
        embedder = get_embedding_provider(req.embedding_provider)
        llm = get_llm_provider(req.llm_provider)
        retriever = Retriever(store=store, embedder=embedder, llm=llm)

        response = retriever.query(
            question=req.question,
            law_names=req.law_names,
            n_results=req.n_results,
            include_sources=req.include_sources,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "answer": response.answer,
        "llm_provider": response.llm_provider,
        "model": response.model,
        "retrieved_chunk_count": response.retrieved_chunk_count,
        "sources": [
            {
                "law_name": s.law_name,
                "article_number": s.article_number,
                "chapter": s.chapter,
                "text": s.text,
                "score": s.score,
                "page": s.page,
            }
            for s in response.sources
        ],
    }


# ---------------------------------------------------------------------------
# GET /rag/documents
# ---------------------------------------------------------------------------

@router.get("/documents", summary="List ingested law documents")
def list_documents():
    """Return metadata for all ingested law documents."""
    _require_lawrag()

    try:
        store = _get_store()
        documents = store.list_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"documents": documents, "count": len(documents)}
