"""LawSyncManager: detect web-side law changes and re-ingest when needed.

Change detection uses a layered strategy so that sources without explicit
modification dates are still handled gracefully:

    Layer 1 – Page date
        If the scraped HTML exposes a modification date *and* a date was stored
        at last ingest, compare them.  Mismatch → re-ingest.

    Layer 2 – HTTP Last-Modified header
        Send a HEAD request and check the ``Last-Modified`` response header.
        If present and a stored date exists, compare them.

    Layer 3 – Content hash
        SHA-256 of sorted article text blocks, stored in the ChromaDB index at
        ingest time.  If a stored hash exists (set by a previous web-ingest),
        compare it with the freshly scraped hash.  Mismatch → re-ingest.

    Layer 4 – Conservative default
        No date or hash available.  ``force_update_on_unknown=True`` (default)
        triggers a re-ingest; set it to ``False`` to skip instead and rely on
        manual ingest for sources that never expose change signals.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional, Tuple

from autocrawler._http import make_session
from autocrawler_law.scrapers import get_law_scraper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(articles: list) -> str:
    """Stable SHA-256 digest of article content suitable for change detection.

    Sorts by article number before hashing so that re-ordering alone does not
    trigger a false-positive update.
    """
    texts = sorted(
        f"{a.get('number', '')}\n{a.get('content', '')}"
        for a in articles
    )
    return hashlib.sha256("\n---\n".join(texts).encode()).hexdigest()[:16]


def _articles_to_text(data: dict) -> str:
    """Synthesise a plain-text document from scraped law data.

    Produces the same logical structure that a PDF extraction would yield so
    that the article-aware chunker can process it correctly.
    """
    lines = []
    current_chapter: Optional[str] = None
    for article in data.get("articles", []):
        ch = article.get("chapter")
        if ch and ch != current_chapter:
            lines.append(f"\n{ch}\n")
            current_chapter = ch
        num = article.get("number", "")
        if num:
            lines.append(num)
        content = article.get("content", "")
        if content:
            lines.append(content)
        for item in article.get("items") or []:
            lines.append(item)
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LawSyncManager
# ---------------------------------------------------------------------------

class LawSyncManager:
    """Check whether a law regulation has changed online and re-ingest if so.

    Args:
        store:                  A :class:`~lawrag.store.chroma.LawChromaStore` instance.
        ingestor:               A :class:`~lawrag.pipeline.ingestor.Ingestor` instance.
        force_update_on_unknown: When no date or stored hash can be compared
                                 (Layer 4), re-ingest anyway if ``True`` (default).
                                 Set to ``False`` to skip silently instead.
    """

    def __init__(
        self,
        store,
        ingestor,
        force_update_on_unknown: bool = True,
    ) -> None:
        self._store = store
        self._ingestor = ingestor
        self.force_update_on_unknown = force_update_on_unknown
        self._session = make_session({
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(
        self,
        url: str,
        law_name: Optional[str] = None,
        verbose: bool = False,
    ) -> dict:
        """Check the law at *url* and re-ingest if the content has changed.

        Args:
            url:      URL of the law regulation page.
            law_name: Override the law name inferred from the scraped page.
            verbose:  Print progress messages.

        Returns:
            A dict with keys:
            - ``law_name``: resolved name of the law
            - ``status``:   ``"up_to_date"`` | ``"updated"`` | ``"error"``
            - ``message``:  human-readable explanation
        """
        scraper = get_law_scraper(url)
        if scraper is None:
            return {
                "law_name": law_name,
                "status": "error",
                "message": f"No scraper available for URL: {url}",
            }

        if verbose:
            print(f"[sync] Scraping {url} …")

        result = scraper.scrape(url)
        if not result["success"]:
            return {
                "law_name": law_name,
                "status": "error",
                "message": result.get("error") or "Scrape failed with unknown error",
            }

        data = result["data"]
        resolved_name = law_name or data.get("law_name")
        if not resolved_name:
            return {
                "law_name": None,
                "status": "error",
                "message": "Could not determine law name from scrape result or argument",
            }

        needs_update, reason = self._needs_update(resolved_name, url, data)

        if not needs_update:
            if verbose:
                print(f"[sync] {resolved_name!r} is up to date — {reason}")
            return {"law_name": resolved_name, "status": "up_to_date", "message": reason}

        if verbose:
            print(f"[sync] {resolved_name!r} needs update — {reason}; re-ingesting …")

        self._ingest_from_scrape(resolved_name, data, verbose=verbose)

        return {"law_name": resolved_name, "status": "updated", "message": reason}

    # ------------------------------------------------------------------
    # Change-detection strategy (layered)
    # ------------------------------------------------------------------

    def _needs_update(
        self,
        law_name: str,
        url: str,
        data: dict,
    ) -> Tuple[bool, str]:
        """Return ``(needs_update, reason)`` using the four-layer strategy."""
        stored_meta = self._store.get_index_metadata(law_name)
        if stored_meta is None:
            return True, "law has not been ingested yet"

        articles = data.get("articles", [])

        # ------------------------------------------------------------------
        # Layer 1: page-provided modification date
        # ------------------------------------------------------------------
        web_date: Optional[str] = data.get("last_modified")
        stored_date: Optional[str] = stored_meta.get("last_modified")

        if web_date and stored_date:
            if web_date != stored_date:
                return True, f"page date changed: {stored_date!r} → {web_date!r}"
            return False, f"page date unchanged ({web_date})"

        # ------------------------------------------------------------------
        # Layer 2: HTTP Last-Modified response header
        # ------------------------------------------------------------------
        http_date = self._head_last_modified(url)
        if http_date and stored_date:
            if http_date != stored_date:
                return True, f"HTTP Last-Modified changed: {stored_date!r} → {http_date!r}"
            return False, "HTTP Last-Modified header unchanged"

        # ------------------------------------------------------------------
        # Layer 3: article content hash
        # Only reliable when the stored hash was written by a previous web-ingest.
        # PDF ingests leave content_hash as None so we skip straight to Layer 4.
        # ------------------------------------------------------------------
        stored_hash: Optional[str] = stored_meta.get("content_hash")
        if stored_hash:
            web_hash = _content_hash(articles)
            if web_hash != stored_hash:
                return True, "article content hash changed"
            return False, "article content hash unchanged"

        # ------------------------------------------------------------------
        # Layer 4: no reliable change signal — use configured default
        # ------------------------------------------------------------------
        if self.force_update_on_unknown:
            logger.warning(
                "[sync] No date or stored hash available for %r; "
                "re-ingesting conservatively (force_update_on_unknown=True).",
                law_name,
            )
            return True, "no date or hash available; forcing update (conservative)"

        logger.warning(
            "[sync] No date or stored hash available for %r; "
            "skipping (force_update_on_unknown=False).",
            law_name,
        )
        return False, "no date or hash available; skipping (force_update_on_unknown=False)"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _head_last_modified(self, url: str) -> Optional[str]:
        """Return the ``Last-Modified`` HTTP header value, or ``None`` on failure."""
        try:
            response = self._session.head(url, timeout=10, allow_redirects=True)
            return response.headers.get("Last-Modified")
        except Exception:
            return None

    def _ingest_from_scrape(
        self,
        law_name: str,
        data: dict,
        verbose: bool = False,
    ) -> None:
        """Re-ingest a law using freshly scraped article data.

        Synthesises plain text from the scraped articles, computes the content
        hash, and calls :meth:`~lawrag.pipeline.ingestor.Ingestor.ingest_text`.
        """
        articles = data.get("articles", [])
        text = _articles_to_text(data)
        source = data.get("source", "web")
        last_modified: Optional[str] = data.get("last_modified")

        web_hash = _content_hash(articles)

        # Determine how we know the modification date
        if last_modified:
            lm_source = "page"
        elif self._head_last_modified is not None:
            # We already called HEAD during _needs_update; reuse result if available.
            # For simplicity, re-use last_modified_source="http_header" only when
            # last_modified was set from the header.  Here we just mark as "content_hash"
            # since we fell through to Layer 3/4.
            lm_source = "content_hash"
        else:
            lm_source = "content_hash"

        self._ingestor.ingest_text(
            text=text,
            law_name=law_name,
            source_file=source,
            last_modified=last_modified,
            content_hash=web_hash,
            last_modified_source=lm_source,
            verbose=verbose,
        )
