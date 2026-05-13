from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class StrategyEvaluator(ABC):
    """Base interface for summarizing realized strategy outputs into evaluation metrics."""

    @abstractmethod
    def evaluate(self, pnl: pd.DataFrame | pd.Series, positions: pd.DataFrame | None = None) -> dict[str, float]:
        """Compute summary metrics such as return, sharpe, drawdown, or turnover."""
