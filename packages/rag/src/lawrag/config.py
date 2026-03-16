"""Environment variable configuration for lawrag."""

import os
from pathlib import Path


def load_dotenv(dotenv_path: str | Path | None = None) -> None:
    """Load a .env file into os.environ (only sets variables not already set).

    Searches for .env in: given path → current directory → parent directories (up to 3 levels).
    """
    candidates: list[Path] = []
    if dotenv_path:
        candidates.append(Path(dotenv_path))
    else:
        cwd = Path.cwd()
        candidates = [cwd / ".env", cwd.parent / ".env", cwd.parent.parent / ".env"]

    for path in candidates:
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            break


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


def get_laws_dir() -> str:
    return os.environ.get("LAWRAG_LAWS_DIR", "./data/laws")
