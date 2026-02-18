"""Anthropic Claude LLM provider."""

from lawrag.providers.base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude (claude-sonnet-4-6)."""

    _MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str) -> None:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "anthropic is required for AnthropicLLMProvider. "
                "Install with: pip install 'lawrag[anthropic]'"
            ) from e

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        message = self._client.messages.create(
            model=self._MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._MODEL
