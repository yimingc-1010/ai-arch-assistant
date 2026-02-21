"""
Law strategy registration plugin.

Registers law-specific URL detectors with the core strategy registry
so that URLAnalyzer can identify law sites without hard-coding them.
"""

from typing import Optional
from urllib.parse import urlparse

from autocrawler.registry import register_strategy


# Law site domain -> strategy name mapping
LAW_SITES = {
    'law.moj.gov.tw': 'law_moj',
    'arkiteki.com': 'law_arkiteki',
}


def detect_law_site(url: str) -> Optional[str]:
    """Detect whether a URL belongs to a known law site.

    Returns:
        Strategy name (e.g. 'law_moj', 'law_arkiteki') or None.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for site_domain, strategy in LAW_SITES.items():
        if site_domain in domain:
            # For arkiteki.com, only match /term/ paths
            if site_domain == 'arkiteki.com':
                if '/term/' in parsed.path:
                    return strategy
            else:
                return strategy

    return None


def register_law_strategies() -> None:
    """Register law site detectors and scrapers with the core registry."""
    register_strategy('law', detect_law_site)
