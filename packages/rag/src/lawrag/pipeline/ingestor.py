"""Ingestor pipeline: PDF → chunks → embeddings → ChromaDB."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from lawrag.pdf.reader import extract_text
from lawrag.pdf.chunker import chunk_document, Chunk
from lawrag.store.chroma import LawChromaStore
from lawrag.providers.base import EmbeddingProvider

# Batch size for embedding API calls
_EMBED_BATCH_SIZE = 64


def _infer_law_name(pdf_path: Path, full_text: str) -> str:
    """Infer the law name from filename or document content.

    Priority:
    1. PDF filename (strip extension and common suffixes)
    2. First meaningful line of the document text
    """
    stem = pdf_path.stem
    # Remove common suffixes like _sample, _v2, _20240101
    stem = re.sub(r"[_\-](sample|v\d+|\d{6,8})$", "", stem, flags=re.IGNORECASE)
    if stem:
        return stem

    # Fallback: first non-empty line
    for line in full_text.splitlines():
        line = line.strip()
        if line and len(line) > 1:
            return line[:30]

    return pdf_path.stem


class Ingestor:
    """Orchestrates the full PDF ingestion pipeline.

    Usage::

        ingestor = Ingestor(store=store, embedder=embedder)
        chunks = ingestor.ingest("建築法.pdf", law_name="建築法")
    """

    def __init__(
        self,
        store: LawChromaStore,
        embedder: EmbeddingProvider,
    ) -> None:
        self._store = store
        self._embedder = embedder

    def ingest(
        self,
        pdf_path: str | Path,
        law_name: Optional[str] = None,
        last_modified: Optional[str] = None,
        verbose: bool = False,
        law_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> List[Chunk]:
        """Ingest a PDF file into the vector store.

        Args:
            pdf_path:      Path to the PDF file.
            law_name:      Override the inferred law name.
            last_modified: Known modification date string (e.g. from a metadata file).
                           When None the index will record no date; sync can still detect
                           changes via content-hash comparison if the law is later re-ingested
                           from a web scrape.
            verbose:       Print progress messages.
            law_type:      Override law hierarchy type (auto-inferred from law_name if None).
            jurisdiction:  Override jurisdiction (auto-inferred from law_name if None).

        Returns:
            List of Chunk objects that were stored.
        """
        pdf_path = Path(pdf_path)

        if verbose:
            print(f"[ingestor] Extracting text from {pdf_path.name} …")

        full_text, page_map = extract_text(pdf_path)

        if not law_name:
            law_name = _infer_law_name(pdf_path, full_text)

        if verbose:
            print(f"[ingestor] Law name: {law_name!r}  |  Total chars: {len(full_text)}")

        chunks = chunk_document(
            full_text=full_text,
            page_map=page_map,
            law_name=law_name,
            source_file=pdf_path.name,
            law_type=law_type,
            jurisdiction=jurisdiction,
        )

        if verbose:
            strategies = {c.strategy for c in chunks}
            print(f"[ingestor] {len(chunks)} chunks produced  |  strategies: {strategies}")

        if not chunks:
            if verbose:
                print("[ingestor] No chunks produced; skipping upsert.")
            return []

        return self._embed_and_store(
            chunks=chunks,
            last_modified=last_modified,
            # PDF ingests don't produce a web-comparable article hash; leave None
            # so the sync manager falls through to its conservative default on first run.
            content_hash=None,
            last_modified_source="page" if last_modified else "unknown",
            verbose=verbose,
        )

    def ingest_text(
        self,
        text: str,
        law_name: str,
        source_file: str = "web",
        last_modified: Optional[str] = None,
        content_hash: Optional[str] = None,
        last_modified_source: str = "unknown",
        verbose: bool = False,
        law_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> List[Chunk]:
        """Ingest pre-extracted law text (e.g. from a web scrape) into the vector store.

        This bypasses PDF extraction and is used by :class:`LawSyncManager` when
        re-ingesting a law directly from its web source.

        Args:
            text:                 Full plain-text content of the law.
            law_name:             Canonical name of the regulation.
            source_file:          Identifier for the source (e.g. a URL or "web").
            last_modified:        Modification date string from the source.
            content_hash:         Pre-computed SHA-256 content hash (from article data).
                                  When provided it is stored in the index for future
                                  change-detection by the sync manager.
            last_modified_source: How the date/hash was obtained.
            verbose:              Print progress messages.
            law_type:             Override law hierarchy type (auto-inferred from law_name if None).
            jurisdiction:         Override jurisdiction (auto-inferred from law_name if None).

        Returns:
            List of Chunk objects that were stored.
        """
        if verbose:
            print(f"[ingestor] Chunking text for {law_name!r}  |  Total chars: {len(text)}")

        chunks = chunk_document(
            full_text=text,
            page_map={0: 1},
            law_name=law_name,
            source_file=source_file,
            law_type=law_type,
            jurisdiction=jurisdiction,
        )

        if verbose:
            strategies = {c.strategy for c in chunks}
            print(f"[ingestor] {len(chunks)} chunks produced  |  strategies: {strategies}")

        if not chunks:
            if verbose:
                print("[ingestor] No chunks produced; skipping upsert.")
            return []

        return self._embed_and_store(
            chunks=chunks,
            last_modified=last_modified,
            content_hash=content_hash,
            last_modified_source=last_modified_source,
            verbose=verbose,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_and_store(
        self,
        chunks: List[Chunk],
        last_modified: Optional[str],
        content_hash: Optional[str],
        last_modified_source: str,
        verbose: bool,
    ) -> List[Chunk]:
        """Embed *chunks* and upsert them (plus metadata) into the store."""
        law_name = chunks[0].law_name
        texts = [c.text for c in chunks]
        vectors: list = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            if verbose:
                print(
                    f"[ingestor] Embedding batch {i // _EMBED_BATCH_SIZE + 1}/"
                    f"{(len(texts) - 1) // _EMBED_BATCH_SIZE + 1} …"
                )
            vectors.extend(self._embedder.embed(batch, input_type="document"))

        if verbose:
            print(f"[ingestor] Upserting {len(chunks)} chunks into ChromaDB …")

        self._store.upsert_chunks(
            chunks=chunks,
            vectors=vectors,
            embedding_model=self._embedder.provider_name,
            last_modified=last_modified,
            content_hash=content_hash,
            last_modified_source=last_modified_source,
        )

        if verbose:
            print(f"[ingestor] Done. {law_name!r} ingested successfully.")

        return chunks
