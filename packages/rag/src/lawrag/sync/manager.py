"""SyncManager: orchestrates scan → diff → ingest pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lawrag.pipeline.ingestor import Ingestor

if TYPE_CHECKING:
    from lawrag.sync.scanner import PDFSource
    from lawrag.store.chroma import LawChromaStore
    from lawrag.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    ingested: list = field(default_factory=list)  # law names successfully ingested
    skipped: list = field(default_factory=list)   # unchanged, skipped
    errors: list = field(default_factory=list)    # "law_name: error message" strings


class SyncManager:
    """Coordinates the full sync flow: scan → compare hashes → ingest changed PDFs."""

    def __init__(
        self,
        source: "PDFSource",
        store: "LawChromaStore",
        embedder: "EmbeddingProvider",
    ) -> None:
        self._source = source
        self._store = store
        self._embedder = embedder

    def run(self, force: bool = False, verbose: bool = False) -> SyncResult:
        """Run the sync pipeline.

        Args:
            force:   Re-ingest all PDFs regardless of hash match.
            verbose: Log per-file progress.

        Returns:
            SyncResult with ingested, skipped, and error lists.
        """
        result = SyncResult()
        ingestor = Ingestor(store=self._store, embedder=self._embedder)

        try:
            entries = self._source.list_pdfs()
        except Exception as exc:
            result.errors.append(f"scan: {exc}")
            return result

        for entry in entries:
            try:
                meta = self._store.get_index_metadata(entry.law_name)
                stored_hash = meta.get("content_hash") if meta else None

                needs_ingest = force or stored_hash is None or stored_hash != entry.content_hash

                if not needs_ingest:
                    if verbose:
                        logger.info("[sync] skip %s (hash unchanged)", entry.law_name)
                    result.skipped.append(entry.law_name)
                    continue

                if verbose:
                    logger.info("[sync] ingesting %s …", entry.law_name)

                ingestor.ingest(
                    entry.path,
                    law_name=entry.law_name,
                    content_hash=entry.content_hash,
                )
                result.ingested.append(entry.law_name)

            except Exception as exc:
                msg = f"{entry.law_name}: {exc}"
                logger.error("[sync] error — %s", msg)
                result.errors.append(msg)

        return result
