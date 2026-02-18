"""AutoCrawler core - automatic web crawling engine."""

from autocrawler.crawler import AutoCrawler, crawl
from autocrawler.analyzer import URLAnalyzer, analyze_url
from autocrawler.html_scraper import HTMLScraper, scrape_html
from autocrawler.api_scraper import APIScraper, scrape_api
from autocrawler.registry import register_strategy, detect_strategy, get_registry

__all__ = [
    "AutoCrawler",
    "crawl",
    "URLAnalyzer",
    "analyze_url",
    "HTMLScraper",
    "scrape_html",
    "APIScraper",
    "scrape_api",
    "register_strategy",
    "detect_strategy",
    "get_registry",
]
