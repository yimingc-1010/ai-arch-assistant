"""Provider factory functions."""

from lawrag.providers.base import EmbeddingProvider, LLMProvider
from lawrag import config


def get_embedding_provider(provider: str | None = None) -> EmbeddingProvider:
    """Return the configured embedding provider.

    Args:
        provider: "voyage" or "openai". Defaults to LAWRAG_EMBEDDING_PROVIDER env var.
    """
    name = provider or config.get_embedding_provider_name()

    if name == "voyage":
        from lawrag.providers.voyage import VoyageEmbeddingProvider
        return VoyageEmbeddingProvider(api_key=config.get_voyage_api_key())

    if name == "openai":
        from lawrag.providers.openai_embeddings import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(api_key=config.get_openai_api_key())

    raise ValueError(f"Unknown embedding provider: {name!r}. Choose 'voyage' or 'openai'.")


def get_llm_provider(provider: str | None = None) -> LLMProvider:
    """Return the configured LLM provider.

    Args:
        provider: "anthropic" or "openai". Defaults to LAWRAG_LLM_PROVIDER env var.
    """
    name = provider or config.get_llm_provider_name()

    if name == "anthropic":
        from lawrag.providers.anthropic_llm import AnthropicLLMProvider
        return AnthropicLLMProvider(api_key=config.get_anthropic_api_key())

    if name == "openai":
        from lawrag.providers.openai_llm import OpenAILLMProvider
        return OpenAILLMProvider(api_key=config.get_openai_api_key())

    raise ValueError(f"Unknown LLM provider: {name!r}. Choose 'anthropic' or 'openai'.")


__all__ = ["EmbeddingProvider", "LLMProvider", "get_embedding_provider", "get_llm_provider"]
