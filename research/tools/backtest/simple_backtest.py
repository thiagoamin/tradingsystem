from __future__ import annotations

import pandas as pd

from research.tools.backtest.base import BacktestEngine


class SimpleBacktestEngine(BacktestEngine):
    """Simple backtest with position lag and optional gross-exposure normalization."""

    def __init__(self, position_lag: int = 1, normalize_exposure: bool = True) -> None:
        if position_lag < 0:
            raise ValueError("position_lag must be >= 0")
        self.position_lag = position_lag
        self.normalize_exposure = normalize_exposure

    def run(self, positions: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
        """Return per-asset pnl using lagged positions and realized next-bar returns."""
        if not positions.index.equals(returns.index):
            raise ValueError("positions and returns must share the same index")
        if list(positions.columns) != list(returns.columns):
            raise ValueError("positions and returns must share the same columns in the same order")
        lagged = positions.shift(self.position_lag).fillna(0.0)
        if self.normalize_exposure:
            gross = lagged.abs().sum(axis=1)
            weights = lagged.div(gross.where(gross != 0.0), axis=0).fillna(0.0)
        else:
            weights = lagged
        return weights * returns
