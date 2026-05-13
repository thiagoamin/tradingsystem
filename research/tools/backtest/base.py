from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BacktestEngine(ABC):
    """Base interface for converting positions and realized returns into backtest outputs."""

    @abstractmethod
    def run(self, positions: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame | pd.Series:
        """Run the backtest and return realized per-period outputs such as pnl."""
