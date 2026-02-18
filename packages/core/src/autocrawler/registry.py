"""
Strategy plugin registration system.

Allows external packages (e.g. autocrawler-law) to register custom
strategy detectors that are consulted by URLAnalyzer before falling
back to the default API/HTML heuristics.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple


# Type for a detector function:
#   (url: str) -> Optional[str]
#   Returns a strategy name (e.g. 'law_moj') or None.
StrategyDetector = Callable[[str], Optional[str]]


class StrategyRegistry:
    """Registry for custom URL strategy detectors."""

    def __init__(self):
        self._detectors: List[Tuple[str, StrategyDetector]] = []

    def register(self, name: str, detector: StrategyDetector) -> None:
        """Register a strategy detector.

        Args:
            name: Human-readable name for the detector (e.g. 'law').
            detector: Callable that takes a URL and returns a strategy
                      name string or None.
        """
        self._detectors.append((name, detector))

    def detect(self, url: str) -> Optional[Dict[str, Any]]:
        """Run all registered detectors against a URL.

        Returns:
            A dict with 'strategy' and 'reason' keys if a detector
            matches, or None.
        """
        for name, detector in self._detectors:
            strategy = detector(url)
            if strategy is not None:
                return {
                    "strategy": strategy,
                    "reason": f"Matched registered detector: {name}",
                }
        return None


# Module-level singleton used by the rest of the system.
_registry = StrategyRegistry()


def register_strategy(name: str, detector: StrategyDetector) -> None:
    """Register a strategy detector on the global registry."""
    _registry.register(name, detector)


def detect_strategy(url: str) -> Optional[Dict[str, Any]]:
    """Run all globally-registered detectors against a URL."""
    return _registry.detect(url)


def get_registry() -> StrategyRegistry:
    """Return the global StrategyRegistry instance."""
    return _registry
