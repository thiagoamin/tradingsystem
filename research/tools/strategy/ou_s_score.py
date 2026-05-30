from __future__ import annotations

"""Stateful trading rules for Ornstein--Uhlenbeck s-scores."""

import numpy as np
import pandas as pd

from research.tools.strategy.base import Strategy


class OUSScoreStrategy(Strategy):
    """Convert OU s-scores into long/short/flat stock-side signals.

    Eligibility restricts opening new positions. Existing positions may still
    close when their exit threshold is crossed, even if the stock is no longer
    eligible for a new trade on that date. A missing score closes a position
    because the strategy lacks a current valid state estimate.
    """

    def __init__(
        self,
        long_entry: float = -1.25,
        short_entry: float = 1.25,
        short_exit: float = 0.75,
        long_exit: float = -0.50,
    ) -> None:
        """Initialize the entry and exit thresholds from the daily baseline."""
        if not long_entry < long_exit < short_exit < short_entry:
            raise ValueError(
                "thresholds must satisfy long_entry < long_exit < short_exit < short_entry"
            )
        self.long_entry = float(long_entry)
        self.short_entry = float(short_entry)
        self.short_exit = float(short_exit)
        self.long_exit = float(long_exit)

    def generate(self, data: pd.DataFrame, eligibility: pd.DataFrame | None = None) -> pd.DataFrame:
        """Return stateful stock-side signals for a panel of OU s-scores.

        Args:
            data: S-score panel, indexed by decision date.
            eligibility: Boolean panel controlling new entries. Missing or
                false values prevent opening a new position.

        Returns:
            Panel with values in ``{-1, 0, 1}``, where positive means long.
        """
        if eligibility is None:
            eligibility = data.notna()
        if not data.index.equals(eligibility.index) or list(data.columns) != list(eligibility.columns):
            raise ValueError("data and eligibility must share the same index and columns")

        positions = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        for symbol in data.columns:
            current = 0.0
            for timestamp, score_value in data[symbol].items():
                score = float(score_value)
                can_enter = bool(eligibility.at[timestamp, symbol])
                if np.isnan(score):
                    current = 0.0
                    positions.at[timestamp, symbol] = current
                    continue
                if current == 0.0 and can_enter:
                    if score < self.long_entry:
                        current = 1.0
                    elif score > self.short_entry:
                        current = -1.0
                elif current > 0.0 and score > self.long_exit:
                    current = 0.0
                elif current < 0.0 and score < self.short_exit:
                    current = 0.0
                positions.at[timestamp, symbol] = current
        return positions
