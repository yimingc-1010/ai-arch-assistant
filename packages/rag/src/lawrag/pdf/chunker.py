"""Law-document-aware chunking strategies for Traditional Chinese regulations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List

from lawrag.pdf.reader import get_page_for_offset

# ---------------------------------------------------------------------------
# Regex patterns for Chinese law structure
# ---------------------------------------------------------------------------

ARTICLE_PATTERN = re.compile(
    r"第\s*[０-９0-9一二三四五六七八九十百千]+\s*條(?:之[０-９0-9一二三四五六七八九]+)?",
    re.UNICODE,
)

CHAPTER_PATTERN = re.compile(
    r"第\s*[０-９0-9一二三四五六七八九十百千]+\s*[章編節](?:\s*[^\n]{1,30})?",
    re.UNICODE,
)

# Sub-item markers: 一、二、三、… or (一)(二)…
SUBITEM_PATTERN = re.compile(
    r"(?:^|\n)(?:[一二三四五六七八九十]+、|\([一二三四五六七八九十]+\))",
    re.UNICODE,
)

SENTENCE_END = re.compile(r"[。！？…]")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    law_name: str
    source_file: str
    article_number: str     # e.g. "第 1 條" or "" for non-article chunks
    chapter: str            # e.g. "第一章 總則" or ""
    text: str
    char_count: int
    strategy: str           # "article" | "sliding_window"
    page_start: int
    page_end: int

    def __post_init__(self) -> None:
        if not self.chunk_id:
            key = f"{self.law_name}{self.article_number}{self.text[:64]}"
            self.chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def chunk_document(
    full_text: str,
    page_map: dict[int, int],
    law_name: str,
    source_file: str,
    max_article_chars: int = 2000,
    window_size: int = 800,
    overlap: int = 150,
) -> List[Chunk]:
    """Split a law document into semantically meaningful chunks.

    Tries article-aware chunking first.  Falls back to sliding-window when
    fewer than 2 articles are detected (e.g. non-structured supplementary docs).

    Args:
        full_text:       NFKC-normalised document text from pdf/reader.py.
        page_map:        char-offset → page-number mapping.
        law_name:        Name of the regulation (用於 chunk_id 與 metadata).
        source_file:     Original PDF filename.
        max_article_chars: Articles longer than this are split at sub-items.
        window_size:     Sliding-window chunk size (fallback).
        overlap:         Sliding-window overlap (fallback).

    Returns:
        List of Chunk objects.
    """
    article_matches = list(ARTICLE_PATTERN.finditer(full_text))

    if len(article_matches) >= 2:
        return _article_chunks(
            full_text, page_map, law_name, source_file,
            article_matches, max_article_chars,
        )

    return _sliding_window_chunks(
        full_text, page_map, law_name, source_file, window_size, overlap,
    )


# ---------------------------------------------------------------------------
# Article-aware chunking (Phase 1)
# ---------------------------------------------------------------------------

def _current_chapter(text_before: str) -> str:
    """Find the last chapter/section heading before the current position."""
    matches = list(CHAPTER_PATTERN.finditer(text_before))
    if matches:
        return matches[-1].group(0).strip()
    return ""


def _make_article_chunk(
    law_name: str,
    source_file: str,
    article_number: str,
    chapter: str,
    text: str,
    page_start: int,
    page_end: int,
    index: int,
) -> Chunk:
    key = f"{law_name}{article_number}{index}"
    chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=chunk_id,
        law_name=law_name,
        source_file=source_file,
        article_number=article_number,
        chapter=chapter,
        text=text.strip(),
        char_count=len(text.strip()),
        strategy="article",
        page_start=page_start,
        page_end=page_end,
    )


def _split_long_article(text: str, max_chars: int) -> List[str]:
    """Split a long article at sub-item boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Try splitting at sub-item markers
    splits = list(SUBITEM_PATTERN.finditer(text))
    if splits:
        parts: List[str] = []
        prev_end = 0
        for match in splits:
            chunk_text = text[prev_end:match.start()]
            if chunk_text.strip():
                parts.append(chunk_text)
            prev_end = match.start()
        tail = text[prev_end:]
        if tail.strip():
            parts.append(tail)
        # Further split if any part is still too long
        result: List[str] = []
        for part in parts:
            if len(part) > max_chars:
                result.extend(_sliding_window_text(part, max_chars, max_chars // 5))
            else:
                result.append(part)
        return result

    # No sub-items: fall back to naive sliding window within the article
    return _sliding_window_text(text, max_chars, max_chars // 5)


def _article_chunks(
    full_text: str,
    page_map: dict[int, int],
    law_name: str,
    source_file: str,
    article_matches: list,
    max_article_chars: int,
) -> List[Chunk]:
    chunks: List[Chunk] = []
    global_index = 0

    for i, match in enumerate(article_matches):
        article_start = match.start()
        article_end = (
            article_matches[i + 1].start()
            if i + 1 < len(article_matches)
            else len(full_text)
        )

        article_text = full_text[article_start:article_end]
        article_number = match.group(0).strip()
        chapter = _current_chapter(full_text[:article_start])
        page_start = get_page_for_offset(article_start, page_map)
        page_end = get_page_for_offset(article_end - 1, page_map)

        parts = _split_long_article(article_text, max_article_chars)
        for part in parts:
            if not part.strip():
                continue
            chunks.append(
                _make_article_chunk(
                    law_name, source_file, article_number, chapter,
                    part, page_start, page_end, global_index,
                )
            )
            global_index += 1

    return chunks


# ---------------------------------------------------------------------------
# Sliding-window fallback (Phase 2)
# ---------------------------------------------------------------------------

def _sliding_window_text(text: str, window: int, overlap: int) -> List[str]:
    """Generic sliding window split on sentence boundaries."""
    parts: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + window, length)

        # Try to break at a sentence boundary within ±50 chars of end
        if end < length:
            search_start = max(start + overlap, end - 50)
            search_end = min(end + 50, length)
            last_sentence = None
            for m in SENTENCE_END.finditer(text, search_start, search_end):
                last_sentence = m.end()
            if last_sentence:
                end = last_sentence

        parts.append(text[start:end])
        if end >= length:
            break
        start = end - overlap

    return parts


def _sliding_window_chunks(
    full_text: str,
    page_map: dict[int, int],
    law_name: str,
    source_file: str,
    window: int,
    overlap: int,
) -> List[Chunk]:
    parts = _sliding_window_text(full_text, window, overlap)
    chunks: List[Chunk] = []
    offset = 0

    for i, part in enumerate(parts):
        if not part.strip():
            offset += len(part)
            continue

        # Locate approximate start offset for page calculation
        start_offset = full_text.find(part[:20], offset)
        if start_offset == -1:
            start_offset = offset
        end_offset = min(start_offset + len(part), len(full_text) - 1)

        key = f"{law_name}sw{i}"
        chunk_id = hashlib.sha256(key.encode()).hexdigest()[:16]

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                law_name=law_name,
                source_file=source_file,
                article_number="",
                chapter="",
                text=part.strip(),
                char_count=len(part.strip()),
                strategy="sliding_window",
                page_start=get_page_for_offset(start_offset, page_map),
                page_end=get_page_for_offset(end_offset, page_map),
            )
        )
        offset += len(part) - overlap

    return chunks
