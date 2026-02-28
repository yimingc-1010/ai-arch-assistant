"""Citation verifier: validate LLM-cited law articles against retrieved sources."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from lawrag.pipeline.retriever import Source


# Pattern matches citations like "建築法第30條", "依建築法第30條之1", etc.
_CITATION_PATTERN = re.compile(
    r"(?:依|依據|根據|按照)?([^\s，。）、]+法[^\s，。）、]*第\s*\d+\s*條(?:之\d+)?)",
    re.UNICODE,
)

# Normalise whitespace inside an article reference for comparison
_WS = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS.sub("", text)


@dataclass
class VerificationResult:
    verified: bool                   # True if all detected citations are valid
    citations_found: List[str]       # All citations detected in the answer
    citations_valid: List[str]       # Citations confirmed in sources
    citations_invalid: List[str]     # Citations not found in sources (potential hallucinations)


class CitationVerifier:
    """Verify that citations in an LLM answer exist in the retrieved sources.

    This does NOT modify the answer; it only annotates which citations are
    supported by evidence and which may be hallucinated.
    """

    def verify(self, answer: str, sources: "List[Source]") -> VerificationResult:
        """Compare answer citations against source metadata.

        Args:
            answer:  The LLM-generated answer text.
            sources: Retrieved source chunks (from RAGResponse.sources).

        Returns:
            VerificationResult with found/valid/invalid citation lists.
        """
        citations_found = [m.group(0) for m in _CITATION_PATTERN.finditer(answer)]

        if not citations_found:
            return VerificationResult(
                verified=True,
                citations_found=[],
                citations_valid=[],
                citations_invalid=[],
            )

        # Build a lookup set from sources: law_name + article_number combos
        source_keys: set[str] = set()
        for src in sources:
            if src.law_name and src.article_number:
                key = _normalise(src.law_name + src.article_number)
                source_keys.add(key)

        valid: List[str] = []
        invalid: List[str] = []

        for cite in citations_found:
            norm_cite = _normalise(cite)
            # Check if any source key is a substring of the citation or vice-versa
            matched = any(
                (sk in norm_cite or norm_cite in sk)
                for sk in source_keys
            )
            if matched:
                valid.append(cite)
            else:
                invalid.append(cite)

        return VerificationResult(
            verified=len(invalid) == 0,
            citations_found=citations_found,
            citations_valid=valid,
            citations_invalid=invalid,
        )
