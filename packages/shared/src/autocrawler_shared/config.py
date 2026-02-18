"""Shared config loading (env vars, etc.)."""

import os
from typing import Any, Dict


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    return {
        "request_timeout": int(os.environ.get("AUTOCRAWLER_TIMEOUT", "30")),
        "user_agent": os.environ.get(
            "AUTOCRAWLER_USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        ),
        "verbose": os.environ.get("AUTOCRAWLER_VERBOSE", "").lower() in ("1", "true"),
    }
