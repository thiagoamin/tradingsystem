from __future__ import annotations

import numpy as np
import pandas as pd

from research.tools.evaluation.base import StrategyEvaluator


class BasicStrategyEvaluator(StrategyEvaluator):
    """Basic evaluator for realized pnl series or per-asset pnl panels."""

    def __init__(self, annualization_factor: float | None = None) -> None:
        if annualization_factor is not None and annualization_factor <= 0:
            raise ValueError("annualization_factor must be > 0 when provided")
        self.annualization_factor = annualization_factor

    def evaluate(self, pnl: pd.DataFrame | pd.Series, positions: pd.DataFrame | None = None) -> dict[str, float]:
        """Compute headline performance metrics from realized pnl."""
        portfolio_pnl = pnl.sum(axis=1) if isinstance(pnl, pd.DataFrame) else pnl.copy()
        portfolio_pnl = portfolio_pnl.fillna(0.0)
        wealth = (1.0 + portfolio_pnl).cumprod()
        running_peak = wealth.cummax()
        drawdown = wealth / running_peak - 1.0
        mean_bar_return = float(portfolio_pnl.mean())
        bar_vol = float(portfolio_pnl.std())
        sharpe = float("nan") if bar_vol == 0.0 else mean_bar_return / bar_vol
        if self.annualization_factor is not None and not np.isnan(sharpe):
            sharpe *= float(np.sqrt(self.annualization_factor))
        turnover = float("nan")
        if positions is not None:
            turnover = float(positions.diff().abs().sum(axis=1).mean())
        return {
            "cum_return": float(wealth.iloc[-1] - 1.0) if not wealth.empty else float("nan"),
            "mean_bar_return": mean_bar_return,
            "bar_vol": bar_vol,
            "sharpe": sharpe,
            "max_drawdown": float(drawdown.min()) if not drawdown.empty else float("nan"),
            "hit_rate": float((portfolio_pnl > 0.0).mean()) if not portfolio_pnl.empty else float("nan"),
            "turnover": turnover,
        }
