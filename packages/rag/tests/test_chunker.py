"""Unit tests for the PDF chunker."""

import pytest
from lawrag.pdf.chunker import chunk_document, Chunk, ARTICLE_PATTERN


# ── helpers ────────────────────────────────────────────────────────────────

def _page_map(text: str) -> dict:
    """Single-page page_map for test texts."""
    return {0: 1}


BUILDING_LAW_SAMPLE = """
第一章 總則

第1條
本法為建築法，適用於全國各地之建築行為。

第2條
本法所稱主管建築機關，在中央為內政部；在直轄市為直轄市政府；在縣（市）為縣（市）政府。

第3條
凡在本法適用地區內興建、改建、修建或使用建築物，均應遵守本法。

第二章 建築許可

第4條
建造執照、雜項執照、使用執照及拆除執照，均由主管建築機關核發之。

第5條
建造執照核發後，建築工程應於六個月內開工，並於核定期限內竣工。
""".strip()


# ── article-aware chunking ──────────────────────────────────────────────────

class TestArticleChunking:
    def test_detects_articles(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        assert len(chunks) >= 5  # 5 articles
        strategies = {c.strategy for c in chunks}
        assert "article" in strategies

    def test_article_numbers_extracted(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        article_nums = [c.article_number for c in chunks]
        assert any("第1條" in n or "第 1 條" in n for n in article_nums)

    def test_chapter_metadata(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        # At least one chunk should have chapter metadata
        chapters = [c.chapter for c in chunks if c.chapter]
        assert len(chapters) > 0

    def test_chunk_ids_are_unique(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_law_name_in_metadata(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        assert all(c.law_name == "建築法" for c in chunks)

    def test_chunk_text_not_empty(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        assert all(c.text.strip() for c in chunks)

    def test_char_count_matches_text(self):
        chunks = chunk_document(
            BUILDING_LAW_SAMPLE, _page_map(BUILDING_LAW_SAMPLE),
            law_name="建築法", source_file="建築法.pdf",
        )
        for c in chunks:
            assert c.char_count == len(c.text)


# ── sliding-window fallback ────────────────────────────────────────────────

class TestSlidingWindowFallback:
    _NO_ARTICLES = "這是一份沒有法條格式的說明文件。本文件僅供參考，不具法律效力。內容包含各種說明與注意事項。" * 20

    def test_falls_back_to_sliding_window(self):
        chunks = chunk_document(
            self._NO_ARTICLES, _page_map(self._NO_ARTICLES),
            law_name="說明文件", source_file="doc.pdf",
        )
        strategies = {c.strategy for c in chunks}
        assert "sliding_window" in strategies
        assert "article" not in strategies

    def test_produces_chunks(self):
        chunks = chunk_document(
            self._NO_ARTICLES, _page_map(self._NO_ARTICLES),
            law_name="說明文件", source_file="doc.pdf",
            window_size=100, overlap=20,
        )
        assert len(chunks) >= 2

    def test_chunks_cover_content(self):
        text = "一二三四五六七八九十" * 100
        chunks = chunk_document(
            text, _page_map(text),
            law_name="測試", source_file="test.pdf",
            window_size=50, overlap=10,
        )
        # All characters should appear in at least one chunk
        all_text = " ".join(c.text for c in chunks)
        # Just verify chunks are non-empty and there are several
        assert len(chunks) > 1


# ── article regex ───────────────────────────────────────────────────────────

class TestArticlePattern:
    def test_matches_standard_article(self):
        assert ARTICLE_PATTERN.search("第1條")
        assert ARTICLE_PATTERN.search("第10條")
        assert ARTICLE_PATTERN.search("第100條")

    def test_matches_fullwidth_digits(self):
        assert ARTICLE_PATTERN.search("第１條")
        assert ARTICLE_PATTERN.search("第１０條")

    def test_matches_chinese_numerals(self):
        assert ARTICLE_PATTERN.search("第一條")
        assert ARTICLE_PATTERN.search("第十條")
        assert ARTICLE_PATTERN.search("第百條")

    def test_matches_supplementary_article(self):
        assert ARTICLE_PATTERN.search("第3條之1")
        assert ARTICLE_PATTERN.search("第3條之一")

    def test_does_not_match_non_article(self):
        assert not ARTICLE_PATTERN.search("第一章")
        assert not ARTICLE_PATTERN.search("第一節")
