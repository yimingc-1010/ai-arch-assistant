"""POST /rag/sync — HMAC-authenticated sync trigger endpoint."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


def _get_webhook_secret() -> str:
    return os.environ.get("WEBHOOK_SECRET", "")


def _verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    """Return True iff the X-Hub-Signature-256 header matches HMAC-SHA256 of body."""
    if not header or not header.startswith("sha256="):
        return False
    provided = header[len("sha256="):]
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, provided)


def _run_sync_background() -> None:
    """Run the full sync pipeline. Called from a BackgroundTask."""
    try:
        from lawrag import config as lawrag_config
        from lawrag.store.chroma import LawChromaStore
        from lawrag.providers import get_embedding_provider
        from lawrag.sync.scanner import LocalPDFScanner
        from lawrag.sync.manager import SyncManager

        laws_dir = Path(lawrag_config.get_laws_dir())
        store = LawChromaStore(persist_dir=lawrag_config.get_chroma_dir())
        embedder = get_embedding_provider()
        scanner = LocalPDFScanner(laws_dir=laws_dir)
        manager = SyncManager(source=scanner, store=store, embedder=embedder)

        result = manager.run(verbose=True)
        logger.info(
            "[sync] complete — ingested=%d skipped=%d errors=%d",
            len(result.ingested), len(result.skipped), len(result.errors),
        )
        if result.errors:
            for err in result.errors:
                logger.error("[sync] error: %s", err)
    except Exception:
        logger.exception("[sync] unexpected error during background sync")


@router.post("/sync", summary="Trigger a law PDF sync (GitHub Actions webhook)", status_code=202)
async def sync_trigger(request: Request, background_tasks: BackgroundTasks):
    """Verify HMAC signature and dispatch sync as a background task.

    Accepts POST with:
      Header: X-Hub-Signature-256: sha256=<hmac-sha256 of body>
      Body:   {} (static JSON body)

    Returns 202 immediately; sync runs in the background.
    """
    secret = _get_webhook_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(body, sig_header, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    background_tasks.add_task(_run_sync_background)
    return {"status": "sync started"}
