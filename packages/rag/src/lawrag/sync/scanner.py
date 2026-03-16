"""PDF source abstraction for the sync pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, runtime_checkable

# Suffix-stripping regex — must match Ingestor._infer_law_name() exactly.
_SUFFIX_RE = re.compile(r"[_\-](sample|v\d+|\d{6,8})$", re.IGNORECASE)


@dataclass
class PDFEntry:
    """A discovered PDF file with pre-computed metadata."""

    path: Path
    law_name: str      # Derived from filename stem (version suffixes stripped)
    content_hash: str  # SHA256 hex digest of raw file bytes


@runtime_checkable  # enables isinstance() checks in tests
class PDFSource(Protocol):
    """Protocol for PDF source implementations (local dir, LFS, etc.)."""

    def list_pdfs(self) -> List[PDFEntry]: ...


class LocalPDFScanner:
    """Scans a local directory for *.pdf files and returns PDFEntry objects.

    Raises FileNotFoundError if the directory does not exist at scan time.
    """

    def __init__(self, laws_dir: Path) -> None:
        self._laws_dir = Path(laws_dir)

    def list_pdfs(self) -> List[PDFEntry]:
        if not self._laws_dir.exists():
            raise FileNotFoundError(
                f"Laws directory not found: {self._laws_dir}. "
                f"Create the directory or set LAWRAG_LAWS_DIR to an existing path."
            )

        entries: List[PDFEntry] = []
        for pdf_path in sorted(self._laws_dir.glob("*.pdf")):
            law_name = _SUFFIX_RE.sub("", pdf_path.stem)
            raw = pdf_path.read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
            entries.append(PDFEntry(path=pdf_path, law_name=law_name, content_hash=content_hash))

        return entries
