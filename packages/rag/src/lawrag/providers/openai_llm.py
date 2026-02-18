"""OpenAI GPT LLM provider."""

from lawrag.providers.base import LLMProvider


class OpenAILLMProvider(LLMProvider):
    """LLM provider backed by OpenAI GPT-4o."""

    _MODEL = "gpt-4o"

    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "openai is required for OpenAILLMProvider. "
                "Install with: pip install 'lawrag[openai]'"
            ) from e

        self._client = OpenAI(api_key=api_key)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._MODEL
