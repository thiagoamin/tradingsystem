from __future__ import annotations

from typing import Dict, Tuple


class FeatureStore:
    """
    In-memory store for latest computed features.

    Stub implementation for later persistence/caching.
    """

    def __init__(self):
        self.features: Dict[Tuple[str, str], float] = {}

    def update(self, updates: Dict[Tuple[str, str], float]) -> None:
        self.features.update(updates)

    def get(self, symbol: str, name: str) -> float:
        return self.features[(symbol, name)]
