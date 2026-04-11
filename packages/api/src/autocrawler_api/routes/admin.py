"""Admin API routes: PDF ingest, URL crawl, task streaming, document listing."""

from __future__ import annotations

import asyncio
import json
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from autocrawler_api.tasks import (
    Task,
    create_task,
    get_task,
    list_tasks,
    task_to_dict,
)

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    from lawrag.pipeline.ingestor import Ingestor
    from lawrag.store.chroma import LawChromaStore
    from lawrag.providers import get_embedding_provider
    from lawrag import config as lawrag_config
    _LAWRAG_AVAILABLE = True
except ImportError:
    _LAWRAG_AVAILABLE = False

try:
    from autocrawler import AutoCrawler
    _CRAWLER_AVAILABLE = True
except ImportError:
    _CRAWLER_AVAILABLE = False

from autocrawler_api.crawl_ingester import crawl_result_to_chunks


# ---------------------------------------------------------------------------
# Router + executor
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin", tags=["admin"])
_executor = ThreadPoolExecutor(max_workers=4)


def _require_lawrag() -> None:
    if not _LAWRAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="lawrag package is not installed. Run: pip install 'lawrag[all]'",
        )


def _require_crawler() -> None:
    if not _CRAWLER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="autocrawler-core package is not installed.",
        )


def _get_store() -> "LawChromaStore":
    return LawChromaStore(persist_dir=lawrag_config.get_chroma_dir())


def _validate_provider(embedding_provider: str) -> None:
    """Raise HTTP 422 immediately if the required API key is missing."""
    if not _LAWRAG_AVAILABLE:
        return
    import os
    key_map = {
        "voyage": ("VOYAGE_API_KEY", "https://dash.voyageai.com"),
        "openai": ("OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
    }
    if embedding_provider not in key_map:
        raise HTTPException(
            status_code=422,
            detail=f"不支援的 embedding provider：{embedding_provider!r}，請選擇 voyage 或 openai",
        )
    env_var, dashboard = key_map[embedding_provider]
    if not os.environ.get(env_var):
        raise HTTPException(
            status_code=422,
            detail=(
                f"環境變數 {env_var} 未設定。"
                f"請在專案根目錄的 .env 檔案中加入 {env_var}=<your-key>，"
                f"或前往 {dashboard} 取得 API key。"
            ),
        )


# ---------------------------------------------------------------------------
# POST /admin/ingest — PDF upload + background ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", summary="Upload a PDF and ingest it asynchronously")
async def start_ingest(
    file: UploadFile = File(...),
    law_name: Optional[str] = Form(None),
    embedding_provider: str = Form("voyage"),
):
    _require_lawrag()
    _validate_provider(embedding_provider)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    task = create_task("ingest_pdf")

    # Write to a temp file outside the request (aiofiles for async write)
    tmp_path = Path(tempfile.mktemp(suffix=".pdf"))
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(contents)

    resolved_law_name = law_name or Path(file.filename).stem
    asyncio.create_task(
        _run_ingest(task.id, tmp_path, resolved_law_name, embedding_provider)
    )
    return {"task_id": task.id}


async def _run_ingest(
    task_id: str,
    tmp_path: Path,
    law_name: str,
    embedding_provider: str,
) -> None:
    task = get_task(task_id)
    if task is None:
        return

    task.status = "running"
    task.message = "準備中..."
    task.progress = 5

    loop = asyncio.get_running_loop()

    def _sync() -> None:
        try:
            task.progress, task.message = 10, "讀取 PDF..."
            store = _get_store()
            embedder = get_embedding_provider(embedding_provider)
            ingestor = Ingestor(store=store, embedder=embedder)

            task.progress, task.message = 30, "分析法條結構..."
            chunks = ingestor.ingest(tmp_path, law_name=law_name)

            task.result = {
                "chunk_count": len(chunks),
                "law_name": chunks[0].law_name if chunks else law_name,
            }
            task.progress = 90
        finally:
            tmp_path.unlink(missing_ok=True)

    try:
        await loop.run_in_executor(_executor, _sync)
        task.status = "done"
        task.progress = 100
        task.message = f"完成！共匯入 {task.result['chunk_count']} 個 chunk"
    except Exception as exc:
        task.status = "error"
        task.error = traceback.format_exc()
        task.message = f"失敗：{exc}"


# ---------------------------------------------------------------------------
# POST /admin/crawl — URL crawl background task
# ---------------------------------------------------------------------------

class CrawlRequest(BaseModel):
    url: str


@router.post("/crawl", summary="Crawl a URL asynchronously")
async def start_crawl(req: CrawlRequest):
    _require_crawler()

    task = create_task("crawl")
    asyncio.create_task(_run_crawl(task.id, req.url))
    return {"task_id": task.id}


async def _run_crawl(task_id: str, url: str) -> None:
    task = get_task(task_id)
    if task is None:
        return

    task.status = "running"
    task.message = f"爬取 {url}..."
    task.progress = 10

    loop = asyncio.get_running_loop()

    def _sync() -> dict:
        crawler = AutoCrawler()
        return crawler.crawl(url)

    try:
        result = await loop.run_in_executor(_executor, _sync)
        task.crawl_data = result
        strategy = result.get("strategy_used", "")
        data = result.get("data") or {}
        articles = data.get("articles", [])
        task.result = {
            "url": url,
            "strategy_used": strategy,
            "article_count": len(articles) if articles else None,
            "title": data.get("title", ""),
        }
        task.status = "done"
        task.progress = 100
        task.message = f"爬取完成（策略: {strategy}）"
    except Exception as exc:
        task.status = "error"
        task.error = traceback.format_exc()
        task.message = f"失敗：{exc}"


# ---------------------------------------------------------------------------
# POST /admin/crawl/{task_id}/ingest — ingest crawl result into vector store
# ---------------------------------------------------------------------------

class IngestCrawlRequest(BaseModel):
    law_name: str
    embedding_provider: str = "voyage"


@router.post("/crawl/{task_id}/ingest", summary="Ingest a crawl result into the vector store")
async def ingest_crawl_result(task_id: str, req: IngestCrawlRequest):
    _require_lawrag()
    _validate_provider(req.embedding_provider)

    crawl_task = get_task(task_id)
    if crawl_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if crawl_task.status != "done":
        raise HTTPException(status_code=400, detail="Crawl task is not complete")
    if crawl_task.crawl_data is None:
        raise HTTPException(status_code=400, detail="No crawl data available")

    ingest_task = create_task("ingest_crawled")
    asyncio.create_task(
        _run_ingest_crawled(
            ingest_task.id,
            crawl_task.crawl_data,
            req.law_name,
            req.embedding_provider,
        )
    )
    return {"task_id": ingest_task.id}


async def _run_ingest_crawled(
    task_id: str,
    crawl_data: dict,
    law_name: str,
    embedding_provider: str,
) -> None:
    task = get_task(task_id)
    if task is None:
        return

    task.status = "running"
    task.message = "轉換爬蟲結果..."
    task.progress = 10

    loop = asyncio.get_running_loop()

    def _sync() -> None:
        task.progress, task.message = 20, "生成 chunks..."
        chunks = crawl_result_to_chunks(crawl_data, law_name)

        if not chunks:
            raise ValueError("沒有可匯入的內容（chunks 為空）")

        task.progress, task.message = 40, "連接向量資料庫..."
        store = _get_store()
        embedder = get_embedding_provider(embedding_provider)

        task.progress, task.message = 50, "生成嵌入向量..."
        texts = [c.text for c in chunks]
        vectors = embedder.embed(texts, input_type="document")

        task.progress, task.message = 80, "寫入 ChromaDB..."
        store.upsert_chunks(
            chunks=chunks,
            vectors=vectors,
            embedding_model=embedder.provider_name,
        )

        task.result = {
            "chunk_count": len(chunks),
            "law_name": law_name,
        }

    try:
        await loop.run_in_executor(_executor, _sync)
        task.status = "done"
        task.progress = 100
        task.message = f"完成！共匯入 {task.result['chunk_count']} 個 chunk"
    except Exception as exc:
        task.status = "error"
        task.error = traceback.format_exc()
        task.message = f"失敗：{exc}"


# ---------------------------------------------------------------------------
# GET /admin/tasks — list all tasks
# ---------------------------------------------------------------------------

@router.get("/tasks", summary="List all tasks")
def get_tasks():
    return {"tasks": [task_to_dict(t) for t in list_tasks()]}


# ---------------------------------------------------------------------------
# GET /admin/tasks/{task_id} — single task
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}", summary="Get a single task")
def get_task_by_id(task_id: str):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_dict(task)


# ---------------------------------------------------------------------------
# GET /admin/tasks/{task_id}/stream — SSE progress stream
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/stream", summary="Stream task progress via SSE")
async def stream_task(task_id: str):
    async def generator():
        while True:
            task = get_task(task_id)
            if task is None:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break
            yield f"data: {json.dumps(task_to_dict(task))}\n\n"
            if task.status in ("done", "error"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /admin/documents — list ingested documents
# ---------------------------------------------------------------------------

@router.get("/documents", summary="List all ingested documents")
def list_documents():
    _require_lawrag()
    try:
        store = _get_store()
        documents = store.list_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"documents": documents, "count": len(documents)}


# ---------------------------------------------------------------------------
# POST /admin/repair — remove orphaned ChromaDB segments
# ---------------------------------------------------------------------------

@router.post("/repair", summary="Remove collections with missing HNSW segment files")
def repair_store():
    """Detect and delete ChromaDB collections whose HNSW index files are missing
    on disk (caused by an interrupted ingest).  Deleted collections can be
    safely re-ingested.  Returns the list of removed collection names."""
    _require_lawrag()
    try:
        store = _get_store()
        deleted = store.repair_orphaned_segments()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"deleted": deleted, "count": len(deleted)}
