"""Unit tests for PDF reader (mocked pdfplumber)."""

import unicodedata
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


class TestExtractText:
    """Tests for lawrag.pdf.reader.extract_text (pdfplumber mocked)."""

    def _make_mock_pdf(self, page_texts: list[str]):
        """Build a mock pdfplumber context manager returning given page texts."""
        mock_page_objs = []
        for text in page_texts:
            page = MagicMock()
            page.extract_text.return_value = text
            mock_page_objs.append(page)

        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = mock_page_objs
        return mock_pdf

    def test_single_page(self):
        from lawrag.pdf.reader import extract_text

        mock_pdf = self._make_mock_pdf(["第１條\n本法為建築法。"])
        with patch("pdfplumber.open", return_value=mock_pdf):
            full_text, page_map = extract_text("fake.pdf")

        # NFKC: fullwidth digit → ASCII
        assert "第1條" in full_text
        assert page_map[0] == 1

    def test_multi_page(self):
        from lawrag.pdf.reader import extract_text

        pages = ["第１條\n內容甲。", "第２條\n內容乙。"]
        mock_pdf = self._make_mock_pdf(pages)
        with patch("pdfplumber.open", return_value=mock_pdf):
            full_text, page_map = extract_text("fake.pdf")

        assert "第1條" in full_text
        assert "第2條" in full_text
        assert len(page_map) == 2
        assert 1 in page_map.values()
        assert 2 in page_map.values()

    def test_nfkc_normalisation(self):
        from lawrag.pdf.reader import extract_text

        # Fullwidth ASCII and Chinese numerals should be normalised
        raw = "Ａ　Ｂ　第１條"
        expected_a = unicodedata.normalize("NFKC", raw)
        mock_pdf = self._make_mock_pdf([raw])
        with patch("pdfplumber.open", return_value=mock_pdf):
            full_text, _ = extract_text("fake.pdf")

        assert full_text == expected_a

    def test_empty_page_handled(self):
        from lawrag.pdf.reader import extract_text

        mock_pdf = self._make_mock_pdf(["", "第1條\n有內容。"])
        with patch("pdfplumber.open", return_value=mock_pdf):
            full_text, page_map = extract_text("fake.pdf")

        assert "第1條" in full_text

    def test_page_map_offsets_correct(self):
        from lawrag.pdf.reader import extract_text, get_page_for_offset

        pages = ["AAAA", "BBBB"]
        mock_pdf = self._make_mock_pdf(pages)
        with patch("pdfplumber.open", return_value=mock_pdf):
            full_text, page_map = extract_text("fake.pdf")

        # Char 0 should be page 1, char after newline should be page 2
        assert get_page_for_offset(0, page_map) == 1
        assert get_page_for_offset(len("AAAA") + 1, page_map) == 2


class TestGetPageForOffset:
    def test_basic(self):
        from lawrag.pdf.reader import get_page_for_offset

        page_map = {0: 1, 100: 2, 200: 3}
        assert get_page_for_offset(0, page_map) == 1
        assert get_page_for_offset(50, page_map) == 1
        assert get_page_for_offset(100, page_map) == 2
        assert get_page_for_offset(150, page_map) == 2
        assert get_page_for_offset(200, page_map) == 3
        assert get_page_for_offset(999, page_map) == 3
