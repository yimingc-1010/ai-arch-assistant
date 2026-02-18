"""ChromaDB wrapper for law regulation chunks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from lawrag.pdf.chunker import Chunk


# The global index collection name
_INDEX_COLLECTION = "__lawrag_index__"


def _law_collection_name(law_name: str) -> str:
    """Map a law name to a safe ChromaDB collection name."""
    # ChromaDB supports UTF-8 names; we still sanitise edge cases.
    safe = law_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"law_{safe}"


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
    ) -> None:
        """Store chunks with their embeddings.

        Args:
            chunks:          List of Chunk objects.
            vectors:         Corresponding embedding vectors (same order).
            embedding_model: Model name string stored in metadata.
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
                }
            )

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # Update global index
        self._update_index(law_name, chunks[0].source_file, len(chunks), ingested_at)

    def _update_index(
        self,
        law_name: str,
        source_file: str,
        chunk_count: int,
        ingested_at: str,
    ) -> None:
        self._index.upsert(
            ids=[law_name],
            documents=[law_name],
            metadatas=[
                {
                    "law_name": law_name,
                    "source_file": source_file,
                    "chunk_count": chunk_count,
                    "ingested_at": ingested_at,
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
    ) -> List[dict]:
        """Retrieve the top-k most relevant chunks.

        Args:
            query_vector: Embedding of the user query.
            law_names:    Filter to these law names. None → search all ingested laws.
            n_results:    Number of results to return in total.

        Returns:
            List of result dicts sorted by score (ascending distance = better).
            Each dict has keys: chunk_id, text, score, and all metadata fields.
        """
        if law_names is None:
            law_names = self.list_law_names()

        if not law_names:
            return []

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
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )

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
