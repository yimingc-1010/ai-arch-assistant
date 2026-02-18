"""AutoCrawler law-specific scraper plugin."""

from autocrawler_law.scrapers import (
    LawScraper,
    MojLawScraper,
    ArkitekiScraper,
    get_law_scraper,
    scrape_law,
)
from autocrawler_law.exporter import export_csv, export_csv_file, export_detailed_csv
from autocrawler_law.plugin import register_law_strategies

__all__ = [
    "LawScraper",
    "MojLawScraper",
    "ArkitekiScraper",
    "get_law_scraper",
    "scrape_law",
    "export_csv",
    "export_csv_file",
    "export_detailed_csv",
    "register_law_strategies",
]
