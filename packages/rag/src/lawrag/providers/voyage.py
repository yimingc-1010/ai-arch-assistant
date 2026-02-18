"""Voyage AI embedding provider using voyage-law-2."""

from typing import List

from lawrag.providers.base import EmbeddingProvider


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding provider optimised for legal documents.

    Uses voyage-law-2 with asymmetric input types:
    - input_type="document" for ingestion
    - input_type="query"    for retrieval
    """

    _DIMENSION = 1024
    _MODEL = "voyage-law-2"

    def __init__(self, api_key: str) -> None:
        try:
            import voyageai  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "voyageai is required for VoyageEmbeddingProvider. "
                "Install with: pip install 'lawrag[anthropic]'"
            ) from e

        self._client = voyageai.Client(api_key=api_key)

    def embed(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        if not texts:
            return []
        result = self._client.embed(texts, model=self._MODEL, input_type=input_type)
        return result.embeddings

    @property
    def dimension(self) -> int:
        return self._DIMENSION

    @property
    def provider_name(self) -> str:
        return "voyage"
