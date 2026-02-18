"""OpenAI embedding provider using text-embedding-3-large."""

from typing import List

from lawrag.providers.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-large (dim=3072)."""

    _DIMENSION = 3072
    _MODEL = "text-embedding-3-large"

    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "openai is required for OpenAIEmbeddingProvider. "
                "Install with: pip install 'lawrag[openai]'"
            ) from e

        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        # OpenAI does not distinguish input types; input_type is ignored.
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._MODEL, input=texts)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._DIMENSION

    @property
    def provider_name(self) -> str:
        return "openai"
