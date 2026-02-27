"""Unit tests for LawSyncManager.

All external I/O (HTTP requests, ChromaDB, embeddings) is mocked.
"""
from unittest.mock import MagicMock, patch, call
import pytest
import responses as responses_lib

from autocrawler_law.sync import LawSyncManager, _content_hash, _articles_to_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_ARTICLES = [
    {"number": "第 1 條", "content": "本法為建築法。", "chapter": "第一章 總則", "items": None},
    {"number": "第 2 條", "content": "主管機關為內政部。", "chapter": "第一章 總則", "items": None},
]

_SAMPLE_DATA = {
    "source": "law.moj.gov.tw",
    "law_name": "建築法",
    "pcode": "D0070109",
    "last_modified": "民國 111 年 05 月 11 日",
    "articles": _SAMPLE_ARTICLES,
    "chapters": [],
}


def _make_scrape_result(success=True, data=None, error=None):
    return {
        "url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109",
        "success": success,
        "data": data or dict(_SAMPLE_DATA),
        "error": error,
    }


def _make_manager(store=None, ingestor=None, force_update_on_unknown=True):
    store = store or MagicMock()
    ingestor = ingestor or MagicMock()
    with patch("autocrawler_law.sync.make_session", return_value=MagicMock()):
        mgr = LawSyncManager(
            store=store,
            ingestor=ingestor,
            force_update_on_unknown=force_update_on_unknown,
        )
    return mgr, store, ingestor


# ---------------------------------------------------------------------------
# _content_hash helper
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_same_articles_produce_same_hash(self):
        h1 = _content_hash(_SAMPLE_ARTICLES)
        h2 = _content_hash(_SAMPLE_ARTICLES)
        assert h1 == h2

    def test_different_content_produces_different_hash(self):
        articles_changed = [
            {"number": "第 1 條", "content": "本法已修正。", "chapter": None, "items": None},
        ]
        assert _content_hash(_SAMPLE_ARTICLES) != _content_hash(articles_changed)

    def test_empty_articles(self):
        h = _content_hash([])
        assert isinstance(h, str)
        assert len(h) == 16  # truncated to 16 hex chars

    def test_order_independent(self):
        """Sorting means article order doesn't affect the hash."""
        reversed_articles = list(reversed(_SAMPLE_ARTICLES))
        assert _content_hash(_SAMPLE_ARTICLES) == _content_hash(reversed_articles)


# ---------------------------------------------------------------------------
# _articles_to_text helper
# ---------------------------------------------------------------------------

class TestArticlesToText:
    def test_basic_conversion(self):
        text = _articles_to_text(_SAMPLE_DATA)
        assert "第一章 總則" in text
        assert "第 1 條" in text
        assert "本法為建築法" in text
        assert "第 2 條" in text

    def test_chapter_appears_once_per_group(self):
        text = _articles_to_text(_SAMPLE_DATA)
        # Chapter heading should appear only once even though two articles share it
        assert text.count("第一章 總則") == 1

    def test_items_included(self):
        data = {
            "articles": [{
                "number": "第 3 條",
                "content": "本法用詞定義如下：",
                "chapter": None,
                "items": ["一、建築物：定著於土地上之工作物。", "二、雜項工作物：其他工作物。"],
            }]
        }
        text = _articles_to_text(data)
        assert "一、建築物" in text
        assert "二、雜項工作物" in text


# ---------------------------------------------------------------------------
# LawSyncManager.sync — routing / error paths
# ---------------------------------------------------------------------------

class TestSyncRouting:
    def test_unsupported_url_returns_error(self):
        mgr, _, _ = _make_manager()
        result = mgr.sync("https://unknown-site.com/law/123")
        assert result["status"] == "error"
        assert "No scraper" in result["message"]

    def test_scrape_failure_returns_error(self):
        mgr, store, _ = _make_manager()
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = _make_scrape_result(
                success=False, data=None, error="Connection refused"
            )
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=X")

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]

    def test_missing_law_name_returns_error(self):
        mgr, store, _ = _make_manager()
        data = dict(_SAMPLE_DATA)
        data["law_name"] = None  # scraper couldn't infer name

        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = _make_scrape_result(success=True, data=data)
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=X")

        assert result["status"] == "error"
        assert "law name" in result["message"].lower()

    def test_not_yet_ingested_triggers_update(self):
        mgr, store, ingestor = _make_manager()
        store.get_index_metadata.return_value = None  # never ingested

        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = _make_scrape_result()
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "updated"
        ingestor.ingest_text.assert_called_once()


# ---------------------------------------------------------------------------
# Layer 1: page date comparison
# ---------------------------------------------------------------------------

class TestLayer1PageDate:
    def _setup(self, web_date, stored_date):
        mgr, store, ingestor = _make_manager()
        store.get_index_metadata.return_value = {
            "law_name": "建築法",
            "last_modified": stored_date,
            "content_hash": None,
            "last_modified_source": "page",
        }
        data = dict(_SAMPLE_DATA)
        data["last_modified"] = web_date
        scrape_result = _make_scrape_result(data=data)
        return mgr, store, ingestor, scrape_result

    def test_same_date_is_up_to_date(self):
        mgr, store, ingestor, scrape = self._setup(
            web_date="民國 111 年 05 月 11 日",
            stored_date="民國 111 年 05 月 11 日",
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "up_to_date"
        ingestor.ingest_text.assert_not_called()

    def test_different_date_triggers_update(self):
        mgr, store, ingestor, scrape = self._setup(
            web_date="民國 112 年 03 月 01 日",
            stored_date="民國 111 年 05 月 11 日",
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "updated"
        assert "page date changed" in result["message"]
        ingestor.ingest_text.assert_called_once()

    def test_updated_ingest_passes_correct_metadata(self):
        mgr, store, ingestor, scrape = self._setup(
            web_date="民國 112 年 03 月 01 日",
            stored_date="民國 111 年 05 月 11 日",
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        call_kwargs = ingestor.ingest_text.call_args[1]
        assert call_kwargs["last_modified"] == "民國 112 年 03 月 01 日"
        assert call_kwargs["content_hash"] is not None  # always computed
        assert call_kwargs["law_name"] == "建築法"


# ---------------------------------------------------------------------------
# Layer 2: HTTP Last-Modified header
# ---------------------------------------------------------------------------

class TestLayer2HttpHeader:
    def _setup(self, http_header_date, stored_date):
        mgr, store, ingestor = _make_manager()
        store.get_index_metadata.return_value = {
            "law_name": "建築法",
            "last_modified": stored_date,
            "content_hash": None,
            "last_modified_source": "http_header",
        }
        # No page-level date
        data = dict(_SAMPLE_DATA)
        data["last_modified"] = None
        scrape_result = _make_scrape_result(data=data)
        # Patch HEAD to return the given date
        mgr._session.head.return_value.headers = {
            "Last-Modified": http_header_date
        }
        return mgr, store, ingestor, scrape_result

    def test_matching_http_header_is_up_to_date(self):
        mgr, store, ingestor, scrape = self._setup(
            http_header_date="Thu, 01 Jan 2026 00:00:00 GMT",
            stored_date="Thu, 01 Jan 2026 00:00:00 GMT",
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "up_to_date"
        ingestor.ingest_text.assert_not_called()

    def test_changed_http_header_triggers_update(self):
        mgr, store, ingestor, scrape = self._setup(
            http_header_date="Fri, 01 Feb 2026 00:00:00 GMT",
            stored_date="Thu, 01 Jan 2026 00:00:00 GMT",
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "updated"
        assert "HTTP Last-Modified" in result["message"]


# ---------------------------------------------------------------------------
# Layer 3: content hash comparison
# ---------------------------------------------------------------------------

class TestLayer3ContentHash:
    def _setup(self, stored_hash, articles):
        mgr, store, ingestor = _make_manager()
        store.get_index_metadata.return_value = {
            "law_name": "建築法",
            "last_modified": None,    # no page date
            "content_hash": stored_hash,
            "last_modified_source": "content_hash",
        }
        # No page-level date, no HTTP header
        data = dict(_SAMPLE_DATA)
        data["last_modified"] = None
        data["articles"] = articles
        scrape_result = _make_scrape_result(data=data)
        mgr._session.head.return_value.headers = {}  # no Last-Modified header
        return mgr, store, ingestor, scrape_result

    def test_same_hash_is_up_to_date(self):
        current_hash = _content_hash(_SAMPLE_ARTICLES)
        mgr, store, ingestor, scrape = self._setup(
            stored_hash=current_hash,
            articles=_SAMPLE_ARTICLES,
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "up_to_date"
        assert "content hash unchanged" in result["message"]
        ingestor.ingest_text.assert_not_called()

    def test_different_hash_triggers_update(self):
        mgr, store, ingestor, scrape = self._setup(
            stored_hash="oldhash0",
            articles=_SAMPLE_ARTICLES,  # produces a different hash
        )
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "updated"
        assert "content hash changed" in result["message"]
        ingestor.ingest_text.assert_called_once()


# ---------------------------------------------------------------------------
# Layer 4: no date / hash — conservative default
# ---------------------------------------------------------------------------

class TestLayer4Conservative:
    def _setup(self, force_update):
        mgr, store, ingestor = _make_manager(force_update_on_unknown=force_update)
        store.get_index_metadata.return_value = {
            "law_name": "建築法",
            "last_modified": None,
            "content_hash": None,       # no stored hash
            "last_modified_source": "unknown",
        }
        data = dict(_SAMPLE_DATA)
        data["last_modified"] = None    # no page date
        scrape_result = _make_scrape_result(data=data)
        mgr._session.head.return_value.headers = {}  # no HTTP header
        return mgr, store, ingestor, scrape_result

    def test_force_true_triggers_update(self):
        mgr, store, ingestor, scrape = self._setup(force_update=True)
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "updated"
        assert "forcing update" in result["message"]
        ingestor.ingest_text.assert_called_once()

    def test_force_false_skips_update(self):
        mgr, store, ingestor, scrape = self._setup(force_update=False)
        with patch("autocrawler_law.sync.get_law_scraper") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.scrape.return_value = scrape
            mock_get.return_value = mock_scraper
            result = mgr.sync("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109")

        assert result["status"] == "up_to_date"
        assert "skipping" in result["message"]
        ingestor.ingest_text.assert_not_called()


# ---------------------------------------------------------------------------
# _head_last_modified — failure tolerance
# ---------------------------------------------------------------------------

class TestHeadLastModified:
    def test_network_error_returns_none(self):
        mgr, _, _ = _make_manager()
        mgr._session.head.side_effect = Exception("Network error")
        result = mgr._head_last_modified("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=X")
        assert result is None

    def test_missing_header_returns_none(self):
        mgr, _, _ = _make_manager()
        mgr._session.head.return_value.headers = {}
        result = mgr._head_last_modified("https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=X")
        assert result is None
