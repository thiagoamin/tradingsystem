from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List

from .utility_functions import UtilityFunction


@dataclass(frozen=True)
class AssetEstimate:
    """Forecast inputs for one symbol."""

    symbol: str
    expected_return: float
    volatility: float


class UtilityAllocator:
    """
    Converts utility scores into portfolio targets for live trading/allocation.

    Flow:
      1) score each asset via UtilityFunction
      2) keep scores above min_score
      3) normalize into weights with optional per-asset max cap
      4) convert weights to integer share targets
    """

    def __init__(
        self,
        utility: UtilityFunction,
        min_score: float = 0.0,
        max_weight: float = 1.0,
        cash_buffer: float = 0.0,
    ):
        if max_weight <= 0:
            raise ValueError("max_weight must be > 0")
        if not (0.0 <= cash_buffer < 1.0):
            raise ValueError("cash_buffer must be in [0, 1)")
        self.utility = utility
        self.min_score = min_score
        self.max_weight = max_weight
        self.cash_buffer = cash_buffer

    def score_assets(self, estimates: Iterable[AssetEstimate]) -> Dict[str, float]:
        """Return utility score per symbol."""
        scores: Dict[str, float] = {}
        for est in estimates:
            score = self.utility.evaluate(est.expected_return, est.volatility)
            if not math.isfinite(score):
                continue
            scores[est.symbol] = score
        return scores

    def target_weights(self, estimates: Iterable[AssetEstimate]) -> Dict[str, float]:
        """Return investable target weights from forecast estimates."""
        raw_scores = self.score_assets(estimates)
        eligible = {sym: s for sym, s in raw_scores.items() if s > self.min_score}
        if not eligible:
            return {}

        total = sum(eligible.values())
        if total <= 0:
            return {}

        raw_weights = {sym: score / total for sym, score in eligible.items()}
        capped_weights = self._apply_max_weight(raw_weights)

        investable = 1.0 - self.cash_buffer
        return {sym: w * investable for sym, w in capped_weights.items() if w > 0}

    def target_quantities(
        self,
        estimates: Iterable[AssetEstimate],
        prices: Dict[str, float],
        equity: float,
    ) -> Dict[str, int]:
        """Convert target weights into whole-share targets."""
        if equity <= 0:
            return {}

        weights = self.target_weights(estimates)
        targets: Dict[str, int] = {}
        for symbol, weight in weights.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue
            targets[symbol] = int((equity * weight) // price)
        return targets

    def _apply_max_weight(self, raw_weights: Dict[str, float]) -> Dict[str, float]:
        """
        Cap each symbol weight by max_weight and redistribute leftover mass.
        """
        remaining = dict(raw_weights)
        final: Dict[str, float] = {sym: 0.0 for sym in raw_weights}
        remaining_mass = 1.0

        while remaining and remaining_mass > 1e-12:
            subtotal = sum(remaining.values())
            if subtotal <= 0:
                break

            progressed = False
            for sym in list(remaining.keys()):
                proportional = remaining_mass * (remaining[sym] / subtotal)
                if proportional >= self.max_weight:
                    final[sym] = self.max_weight
                    remaining_mass -= self.max_weight
                    del remaining[sym]
                    progressed = True

            if not progressed:
                for sym, score in remaining.items():
                    final[sym] = remaining_mass * (score / subtotal)
                remaining.clear()

        # Keep unallocated mass as cash (do not renormalize).
        return {sym: w for sym, w in final.items() if w > 0}
