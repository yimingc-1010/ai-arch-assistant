"""Unit tests for provider factory and provider classes (all SDKs mocked via sys.modules)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock
import pytest


def _inject_module(name: str, **attrs) -> MagicMock:
    """Inject a fake module into sys.modules and return it."""
    mod = MagicMock(spec=ModuleType(name))
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _remove_modules(*names: str) -> None:
    for name in names:
        sys.modules.pop(name, None)


class TestProviderFactory:
    def test_get_embedding_provider_voyage(self, monkeypatch):
        mock_client_cls = MagicMock()
        _inject_module("voyageai", Client=mock_client_cls)
        monkeypatch.setenv("VOYAGE_API_KEY", "test_key")
        # Remove cached provider module so it re-imports
        _remove_modules("lawrag.providers.voyage")

        from lawrag.providers import get_embedding_provider
        provider = get_embedding_provider("voyage")
        assert provider.provider_name == "voyage"

        _remove_modules("voyageai", "lawrag.providers.voyage")

    def test_get_embedding_provider_openai(self, monkeypatch):
        mock_openai_cls = MagicMock()
        _inject_module("openai", OpenAI=mock_openai_cls)
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        _remove_modules("lawrag.providers.openai_embeddings")

        from lawrag.providers import get_embedding_provider
        provider = get_embedding_provider("openai")
        assert provider.provider_name == "openai"

        _remove_modules("openai", "lawrag.providers.openai_embeddings")

    def test_get_embedding_provider_invalid(self):
        from lawrag.providers import get_embedding_provider
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider("invalid_provider")

    def test_get_llm_provider_anthropic(self, monkeypatch):
        mock_anthropic_cls = MagicMock()
        _inject_module("anthropic", Anthropic=mock_anthropic_cls)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
        _remove_modules("lawrag.providers.anthropic_llm")

        from lawrag.providers import get_llm_provider
        provider = get_llm_provider("anthropic")
        assert provider.provider_name == "anthropic"

        _remove_modules("anthropic", "lawrag.providers.anthropic_llm")

    def test_get_llm_provider_openai(self, monkeypatch):
        mock_openai_cls = MagicMock()
        _inject_module("openai", OpenAI=mock_openai_cls)
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        _remove_modules("lawrag.providers.openai_llm")

        from lawrag.providers import get_llm_provider
        provider = get_llm_provider("openai")
        assert provider.provider_name == "openai"

        _remove_modules("openai", "lawrag.providers.openai_llm")

    def test_get_llm_provider_invalid(self):
        from lawrag.providers import get_llm_provider
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider("invalid_provider")


class TestVoyageProvider:
    def _make_provider(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3]]
        mock_client = MagicMock()
        mock_client.embed.return_value = mock_result
        mock_client_cls = MagicMock(return_value=mock_client)

        _inject_module("voyageai", Client=mock_client_cls)
        _remove_modules("lawrag.providers.voyage")

        from lawrag.providers.voyage import VoyageEmbeddingProvider
        provider = VoyageEmbeddingProvider(api_key="test")
        return provider, mock_client

    def test_embed_calls_client(self):
        provider, mock_client = self._make_provider()
        result = provider.embed(["test text"], input_type="document")
        mock_client.embed.assert_called_once_with(
            ["test text"], model="voyage-law-2", input_type="document"
        )
        assert result == [[0.1, 0.2, 0.3]]

    def test_embed_uses_query_input_type(self):
        provider, mock_client = self._make_provider()
        mock_client.embed.return_value.embeddings = [[0.9, 0.8]]
        provider.embed(["query text"], input_type="query")
        mock_client.embed.assert_called_with(
            ["query text"], model="voyage-law-2", input_type="query"
        )

    def test_dimension(self):
        provider, _ = self._make_provider()
        assert provider.dimension == 1024

    def test_empty_texts_returns_empty(self):
        provider, mock_client = self._make_provider()
        result = provider.embed([])
        assert result == []
        mock_client.embed.assert_not_called()


class TestAnthropicProvider:
    def _make_provider(self):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="測試回答")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_cls = MagicMock(return_value=mock_client)

        _inject_module("anthropic", Anthropic=mock_anthropic_cls)
        _remove_modules("lawrag.providers.anthropic_llm")

        from lawrag.providers.anthropic_llm import AnthropicLLMProvider
        provider = AnthropicLLMProvider(api_key="test")
        return provider, mock_client

    def test_complete_returns_text(self):
        provider, mock_client = self._make_provider()
        result = provider.complete(system="sys", user="user msg")
        assert result == "測試回答"
        mock_client.messages.create.assert_called_once()

    def test_complete_passes_params(self):
        provider, mock_client = self._make_provider()
        provider.complete(system="s", user="u", max_tokens=512, temperature=0.5)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["temperature"] == 0.5

    def test_model_name(self):
        provider, _ = self._make_provider()
        assert provider.model_name == "claude-sonnet-4-6"

    def test_provider_name(self):
        provider, _ = self._make_provider()
        assert provider.provider_name == "anthropic"
