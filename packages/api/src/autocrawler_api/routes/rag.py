"""REST API routes for the lawrag RAG system."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import List, Literal, Optional

try:
    from fastapi import APIRouter, File, Form, HTTPException, UploadFile
    from fastapi.responses import JSONResponse, StreamingResponse
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
    output_format: Literal["prose", "checklist"] = "prose"
    verify_citations: bool = False
    jurisdictions: Optional[List[str]] = None


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
            output_format=req.output_format,
            verify_citations=req.verify_citations,
            jurisdictions=req.jurisdictions,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result: dict = {
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
    if response.verification is not None:
        v = response.verification
        result["verification"] = {
            "verified": v.verified,
            "citations_found": v.citations_found,
            "citations_valid": v.citations_valid,
            "citations_invalid": v.citations_invalid,
        }
    return result


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


# ---------------------------------------------------------------------------
# POST /rag/query/stream  — SSE streaming answer
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一位專業的法律助理，專門解答關於中華民國法規的問題。
請根據以下提供的法條內容來回答問題。
- 回答時請引用相關法條（例如：依建築法第30條）
- 如果提供的法條不足以回答問題，請明確說明
- 請使用繁體中文回答"""

_CHECKLIST_SYSTEM_PROMPT = """你是一位專業的建築法規合規顧問。
請根據以下法條，以 Markdown 核取清單格式（- [ ] 項目）回答問題。
每個項目須附上法條依據，格式：- [ ] 說明（依建築法第X條）
請以繁體中文回答，清單盡量精確具體、可操作。
如果提供的法條不足以回答問題，請明確說明。"""

_STREAM_MODEL = "claude-sonnet-4-6"


@router.post("/query/stream", summary="Stream a legal question answer via SSE")
async def stream_query_rag(req: QueryRequest):
    """Query the RAG system and stream the LLM answer token by token.

    SSE event types:
    - ``{"type": "sources", "sources": [...], "retrieved_chunk_count": N}``
    - ``{"type": "token",   "text": "..."}``
    - ``{"type": "done",    "model": "...", "provider": "..."}``
    - ``{"type": "error",   "message": "..."}``
    """
    _require_lawrag()

    async def generate():
        try:
            loop = asyncio.get_running_loop()

            # ------------------------------------------------------------------
            # Step 1+2: embed query + retrieve chunks (blocking → thread)
            # ------------------------------------------------------------------
            def _retrieve():
                store = _get_store()
                embedder = get_embedding_provider(req.embedding_provider)
                query_vec = embedder.embed([req.question], input_type="query")[0]
                return store.query(
                    query_vector=query_vec,
                    law_names=req.law_names,
                    n_results=req.n_results,
                    jurisdictions=req.jurisdictions,
                )

            results = await loop.run_in_executor(None, _retrieve)

            # ------------------------------------------------------------------
            # Step 3: emit sources event
            # ------------------------------------------------------------------
            sources = [
                {
                    "law_name": r.get("law_name", ""),
                    "article_number": r.get("article_number", ""),
                    "chapter": r.get("chapter", ""),
                    "text": r.get("text", ""),
                    "score": float(r.get("score", 0.0)),
                    "page": int(r.get("page_start", 1)),
                }
                for r in results
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'retrieved_chunk_count': len(results)})}\n\n"

            # ------------------------------------------------------------------
            # Step 4: build context (same logic as Retriever.query)
            # ------------------------------------------------------------------
            context_parts: List[str] = []
            for r in results:
                header = f"【{r['law_name']}】"
                if r.get("chapter"):
                    header += f" {r['chapter']}"
                if r.get("article_number"):
                    header += f" {r['article_number']}"
                context_parts.append(f"{header}\n{r['text']}")

            context = "\n\n---\n\n".join(context_parts)
            user_message = (
                f"以下是相關法條內容：\n\n{context}\n\n---\n\n問題：{req.question}"
            )

            # ------------------------------------------------------------------
            # Step 5: stream LLM tokens with AsyncAnthropic
            # ------------------------------------------------------------------
            try:
                import anthropic as _anthropic
            except ImportError as exc:
                raise ImportError("anthropic package is required") from exc

            stream_system = (
                _CHECKLIST_SYSTEM_PROMPT
                if req.output_format == "checklist"
                else _SYSTEM_PROMPT
            )
            client = _anthropic.AsyncAnthropic(
                api_key=lawrag_config.get_anthropic_api_key()
            )
            async with client.messages.stream(
                model=_STREAM_MODEL,
                max_tokens=2048,
                temperature=0.0,
                system=stream_system,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'model': _STREAM_MODEL, 'provider': 'anthropic'})}\n\n"

        except Exception as exc:
            import traceback
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc), 'traceback': traceback.format_exc()})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
