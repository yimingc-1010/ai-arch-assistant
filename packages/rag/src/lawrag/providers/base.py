"""Abstract base classes for embedding and LLM providers."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        """Embed a list of texts.

        Args:
            texts: List of strings to embed.
            input_type: "document" for ingestion, "query" for retrieval (asymmetric embeddings).

        Returns:
            List of embedding vectors.
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """Generate a completion.

        Args:
            system: System prompt.
            user: User message.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            Generated text response.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        ...
