from __future__ import annotations

from typing import Dict, Tuple

from research.fetchers.models import OHLCVBar


class FeatureEngine:
    """
    Stateful indicator/feature computation.

    Stub implementation: maintains minimal history and emits no features yet.
    """

    def __init__(self):
        self.history: Dict[str, list[OHLCVBar]] = {}

    def on_bar(self, bar: OHLCVBar) -> Dict[Tuple[str, str], float]:
        history = self.history.setdefault(bar.symbol, [])
        history.append(bar)
        # TODO: compute indicators (returns, moving averages, volatility, etc.)
        return {}
