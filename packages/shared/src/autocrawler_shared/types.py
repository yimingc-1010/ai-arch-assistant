"""Common TypedDicts, enums, and protocols used across packages."""

from typing import Any, Dict, List, Optional, TypedDict


class ScrapeResult(TypedDict, total=False):
    """Result from an individual scraper (HTML, API, or law)."""
    url: str
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]


class CrawlResult(TypedDict, total=False):
    """Result from AutoCrawler.crawl()."""
    url: str
    timestamp: str
    strategy_analysis: Optional[Dict[str, Any]]
    strategy_used: Optional[str]
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
