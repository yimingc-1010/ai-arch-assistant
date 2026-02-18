"""Environment variable configuration for lawrag."""

import os


def get_chroma_dir() -> str:
    return os.environ.get("LAWRAG_CHROMA_DIR", "./data/chroma")


def get_embedding_provider_name() -> str:
    return os.environ.get("LAWRAG_EMBEDDING_PROVIDER", "voyage")


def get_llm_provider_name() -> str:
    return os.environ.get("LAWRAG_LLM_PROVIDER", "anthropic")


def get_voyage_api_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY", "")
    return key


def get_anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key


def get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    return key
