"""Convert AutoCrawler results into Chunk objects for ingestion."""

from __future__ import annotations

import hashlib
from typing import List

try:
    from lawrag.pdf.chunker import Chunk
    _LAWRAG_AVAILABLE = True
except ImportError:
    _LAWRAG_AVAILABLE = False


def _sliding_window_text(text: str, window: int = 800, overlap: int = 150) -> List[str]:
    """Simple sliding-window split (no page map needed for web content)."""
    parts: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + window, length)
        parts.append(text[start:end])
        if end >= length:
            break
        start = end - overlap
    return parts


def _sliding_window_chunks(content: str, law_name: str, source_url: str) -> List["Chunk"]:
    parts = _sliding_window_text(content)
    chunks: List[Chunk] = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        key = f"{law_name}sw{i}{source_url}"
        chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        chunks.append(Chunk(
            chunk_id=chunk_id,
            law_name=law_name,
            source_file=source_url,
            article_number="",
            chapter="",
            text=part.strip(),
            char_count=len(part.strip()),
            strategy="sliding_window",
            page_start=1,
            page_end=1,
        ))
    return chunks


def crawl_result_to_chunks(crawl_result: dict, law_name: str) -> List["Chunk"]:
    """Convert an AutoCrawler.crawl() result dict into Chunk objects.

    Structured law strategies (law_moj, law_arkiteki) → one Chunk per article.
    Generic HTML/API pages → sliding-window chunks over the text content.
    """
    if not _LAWRAG_AVAILABLE:
        raise ImportError("lawrag is required for crawl ingestion")

    strategy = crawl_result.get("strategy_used", "")
    data = crawl_result.get("data") or {}
    source_url = crawl_result.get("url", "")

    if strategy in ("law_moj", "law_arkiteki"):
        chunks: List[Chunk] = []
        current_chapter = ""
        for article in data.get("articles", []):
            if article.get("chapter"):
                current_chapter = article["chapter"]
            text = article.get("content", "")
            if not text.strip():
                continue
            article_num = article.get("number", "")
            chunk_id = hashlib.sha256(
                f"{law_name}{article_num}{source_url}".encode()
            ).hexdigest()[:16]
            chunks.append(Chunk(
                chunk_id=chunk_id,
                law_name=law_name,
                source_file=source_url,
                article_number=article_num,
                chapter=current_chapter,
                text=text,
                char_count=len(text),
                strategy="article",
                page_start=1,
                page_end=1,
            ))
        return chunks

    # General web page: extract content text
    content = (
        data.get("content")
        or data.get("text")
        or data.get("body")
        or ""
    )
    if not content:
        return []
    return _sliding_window_chunks(content, law_name, source_url)
