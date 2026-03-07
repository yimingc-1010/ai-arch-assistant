"""ChromaDB wrapper for law regulation chunks."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from lawrag.pdf.chunker import Chunk

# Sentinel used to store None in ChromaDB metadata (which requires str/int/float/bool)
_NONE_SENTINEL = ""


# The global index collection name
_INDEX_COLLECTION = "lawrag.index"


def _law_collection_name(law_name: str) -> str:
    """Map a law name to a ChromaDB-safe collection name.

    ChromaDB only allows [a-zA-Z0-9._-], starting/ending with [a-zA-Z0-9].
    We use a short SHA256 hash so any law name (including Chinese) maps safely.
    Format: law-<8-char-hex>  e.g. law-3f2a1b4c
    """
    digest = hashlib.sha256(law_name.encode()).hexdigest()[:8]
    return f"law-{digest}"


class LawChromaStore:
    """ChromaDB-backed vector store for law regulation chunks.

    Each law regulation is stored in its own collection so that per-law
    filtering is efficient.  A lightweight index collection tracks which
    laws have been ingested.
    """

    def __init__(self, persist_dir: str | Path = "./data/chroma") -> None:
        try:
            import chromadb  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "chromadb is required. Install with: pip install lawrag"
            ) from e

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        # Ensure index collection exists
        self._index = self._client.get_or_create_collection(_INDEX_COLLECTION)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        chunks: List[Chunk],
        vectors: List[List[float]],
        embedding_model: str,
        last_modified: Optional[str] = None,
        content_hash: Optional[str] = None,
        last_modified_source: str = "unknown",
    ) -> None:
        """Store chunks with their embeddings.

        Args:
            chunks:               List of Chunk objects.
            vectors:              Corresponding embedding vectors (same order).
            embedding_model:      Model name string stored in metadata.
            last_modified:        Source-provided modification date (ISO or ROC calendar string).
            content_hash:         SHA256 hex digest of article content used for change detection.
            last_modified_source: How the date was obtained: "page" | "http_header" |
                                  "content_hash" | "unknown".
        """
        if not chunks:
            return

        law_name = chunks[0].law_name
        collection = self._client.get_or_create_collection(
            _law_collection_name(law_name),
            metadata={"hnsw:space": "cosine"},
        )

        ingested_at = datetime.now(timezone.utc).isoformat()

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for chunk, vec in zip(chunks, vectors):
            ids.append(chunk.chunk_id)
            embeddings.append(vec)
            documents.append(chunk.text)
            metadatas.append(
                {
                    "law_name": chunk.law_name,
                    "source_file": chunk.source_file,
                    "article_number": chunk.article_number,
                    "chapter": chunk.chapter,
                    "char_count": chunk.char_count,
                    "strategy": chunk.strategy,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "embedding_model": embedding_model,
                    "ingested_at": ingested_at,
                    "last_modified": last_modified or _NONE_SENTINEL,
                    "law_type": chunk.law_type,
                    "jurisdiction": chunk.jurisdiction,
                }
            )

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # Update global index
        self._update_index(
            law_name,
            chunks[0].source_file,
            len(chunks),
            ingested_at,
            last_modified=last_modified,
            content_hash=content_hash,
            last_modified_source=last_modified_source,
        )

    def _update_index(
        self,
        law_name: str,
        source_file: str,
        chunk_count: int,
        ingested_at: str,
        last_modified: Optional[str] = None,
        content_hash: Optional[str] = None,
        last_modified_source: str = "unknown",
    ) -> None:
        # Use hash as id (ChromaDB ids must be ASCII-safe strings)
        law_id = hashlib.sha256(law_name.encode()).hexdigest()[:16]
        self._index.upsert(
            ids=[law_id],
            documents=[law_name],
            metadatas=[
                {
                    "law_name": law_name,
                    "source_file": source_file,
                    "chunk_count": chunk_count,
                    "ingested_at": ingested_at,
                    "last_modified": last_modified or _NONE_SENTINEL,
                    "content_hash": content_hash or _NONE_SENTINEL,
                    "last_modified_source": last_modified_source,
                }
            ],
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_vector: List[float],
        law_names: Optional[List[str]] = None,
        n_results: int = 5,
        jurisdictions: Optional[List[str]] = None,
        law_types: Optional[List[str]] = None,
    ) -> List[dict]:
        """Retrieve the top-k most relevant chunks.

        Args:
            query_vector:  Embedding of the user query.
            law_names:     Filter to these law names. None → search all ingested laws.
            n_results:     Number of results to return in total.
            jurisdictions: Filter to these jurisdictions (e.g. ["台北市", "全國"]).
            law_types:     Filter to these law hierarchy types (e.g. ["母法", "子法"]).

        Returns:
            List of result dicts sorted by score (ascending distance = better).
            Each dict has keys: chunk_id, text, score, and all metadata fields.
        """
        if law_names is None:
            law_names = self.list_law_names()

        if not law_names:
            return []

        # Build ChromaDB where clause for metadata filtering
        where_clause = self._build_where_clause(jurisdictions, law_types)

        all_results: List[dict] = []

        for name in law_names:
            col_name = _law_collection_name(name)
            try:
                collection = self._client.get_collection(col_name)
            except Exception:
                continue  # law not yet ingested

            col_count = collection.count()
            if col_count == 0:
                continue

            k = min(n_results, col_count)
            query_kwargs: dict = {
                "query_embeddings": [query_vector],
                "n_results": k,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_clause:
                query_kwargs["where"] = where_clause

            results = collection.query(**query_kwargs)

            ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            for cid, doc, meta, dist in zip(ids, documents, metadatas, distances):
                all_results.append(
                    {
                        "chunk_id": cid,
                        "text": doc,
                        "score": dist,  # cosine distance; lower = more similar
                        **meta,
                    }
                )

        # Sort by score (lowest cosine distance first) and return top-k
        all_results.sort(key=lambda x: x["score"])
        return all_results[:n_results]

    def _build_where_clause(
        self,
        jurisdictions: Optional[List[str]],
        law_types: Optional[List[str]],
    ) -> Optional[dict]:
        """Build a ChromaDB where clause from filter lists."""
        conditions = []
        if jurisdictions:
            conditions.append({"jurisdiction": {"$in": jurisdictions}})
        if law_types:
            conditions.append({"law_type": {"$in": law_types}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_documents(self) -> List[dict]:
        """Return metadata for all ingested documents from the index."""
        count = self._index.count()
        if count == 0:
            return []

        result = self._index.get(include=["metadatas"])
        metadatas = result.get("metadatas") or []
        return list(metadatas)

    def list_law_names(self) -> List[str]:
        """Return names of all ingested law regulations."""
        docs = self.list_documents()
        return [d["law_name"] for d in docs]

    def get_index_metadata(self, law_name: str) -> Optional[dict]:
        """Return index metadata for a specific law, or None if not ingested.

        Normalises sentinel empty strings back to None for optional fields
        (last_modified, content_hash) so callers can use simple truthiness checks.
        """
        law_id = hashlib.sha256(law_name.encode()).hexdigest()[:16]
        result = self._index.get(ids=[law_id], include=["metadatas"])
        metadatas = result.get("metadatas") or []
        if not metadatas:
            return None
        meta = dict(metadatas[0])
        for field in ("last_modified", "content_hash"):
            if meta.get(field) == _NONE_SENTINEL:
                meta[field] = None
        return meta
