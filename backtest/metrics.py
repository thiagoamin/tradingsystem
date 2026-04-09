"""
backtest/metrics.py
===================
Performance metrics for daily return series.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MetricSet:
    label: str
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float

    def __str__(self) -> str:
        return (
            f"{self.label:<22}  CAGR={self.cagr:+.2%}  Vol={self.vol:.2%}"
            f"  Sharpe={self.sharpe:.2f}  MaxDD={self.max_drawdown:.2%}"
        )


def calc_metrics(daily_returns: pd.Series, label: str) -> MetricSet:
    """
    Compute annualised performance metrics from a daily return series.
    """
    r = daily_returns.dropna()
    ann_ret = r.mean() * 252
    ann_vol = r.std() * np.sqrt(252)
    sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0.0
    cum     = (1 + r).cumprod()
    max_dd  = (cum / cum.cummax() - 1).min()
    return MetricSet(label=label, cagr=ann_ret, vol=ann_vol, sharpe=sharpe, max_drawdown=max_dd)
