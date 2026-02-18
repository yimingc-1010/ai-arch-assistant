"""PDF text extraction optimised for Traditional Chinese law documents."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Tuple


def extract_text(pdf_path: str | Path) -> Tuple[str, dict[int, int]]:
    """Extract full text from a PDF and build a character-offset → page mapping.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Tuple of:
        - full_text: Normalised NFKC string of all pages concatenated with newlines.
        - page_map: Dict mapping starting character offset (in full_text) to the
          1-based page number.  Use this to recover the page number for any chunk.
    """
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "pdfplumber is required for PDF extraction. "
            "Install with: pip install lawrag"
        ) from e

    pdf_path = Path(pdf_path)
    pages_text: list[str] = []

    with pdfplumber.open(
        str(pdf_path),
        laparams={"all_texts": True},
    ) as pdf:
        for page in pdf.pages:
            raw = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            # NFKC: convert fullwidth digits/letters to ASCII equivalents
            # e.g. 第１條 → 第1條, Ａ → A
            normalised = unicodedata.normalize("NFKC", raw)
            pages_text.append(normalised)

    # Build page_map: char_offset → page_number (1-based)
    page_map: dict[int, int] = {}
    offset = 0
    for page_num, text in enumerate(pages_text, start=1):
        page_map[offset] = page_num
        offset += len(text) + 1  # +1 for the joining newline

    full_text = "\n".join(pages_text)
    return full_text, page_map


def get_page_for_offset(offset: int, page_map: dict[int, int]) -> int:
    """Return the page number that contains the given character offset.

    Args:
        offset: Character offset in the full text.
        page_map: The page_map returned by extract_text().

    Returns:
        1-based page number.
    """
    page = 1
    for start_offset, page_num in sorted(page_map.items()):
        if start_offset <= offset:
            page = page_num
        else:
            break
    return page
