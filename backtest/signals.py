"""
Portfolio-level signals: produce a cross-sectional expected-return vector
at each rebalance date.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np
import pandas as pd


class PortfolioSignal(ABC):
    @abstractmethod
    def compute(self, close: pd.DataFrame, date: pd.Timestamp, assets: List[str]) -> np.ndarray:
        """
        Return a 1-D expected-return array aligned to ``assets``.
        """
        ...


class MomentumReversalSignal(PortfolioSignal):
    """
    Risk-adjusted composite momentum + short-term reversal, z-scored cross-sectionally.

    For each asset:
        trend = Σ mom_weight[i] * (price[t] / price[t - window[i]] - 1)
        risk_adj_trend = trend / annualised_vol
        score = risk_adj_trend - beta_rev * 1m_return  (reversal on 1m)

    Scores are z-scored cross-sectionally and scaled by ``c_signal``.
    """

    def __init__(self, mom_windows: List[int], mom_weights: List[float], beta_rev: float = 0.15, 
                 c_signal: float = 0.02, vol_window: int = 63):
        self.mom_windows = mom_windows
        self.mom_weights = mom_weights
        self.beta_rev = beta_rev
        self.c_signal = c_signal
        self.vol_window = vol_window

    def compute(self, close: pd.DataFrame, date: pd.Timestamp, assets: List[str]) -> np.ndarray:
        loc = close.index.get_loc(date)
        scores = np.zeros(len(assets))

        for i, asset in enumerate(assets):
            p = close[asset].values
            moms = [
                p[loc] / p[loc - w] - 1 if loc >= w else 0.0
                for w in self.mom_windows
            ]
            trend = sum(wt * m for wt, m in zip(self.mom_weights, moms))
            vol = (
                close[asset]
                .iloc[max(0, loc - self.vol_window) : loc + 1]
                .pct_change()
                .std()
                * np.sqrt(252)
            )
            vol = max(vol, 1e-6)
            scores[i] = trend / vol + self.beta_rev * (-moms[0])

        mu, sd = scores.mean(), scores.std()
        if sd < 1e-8:
            return np.zeros(len(assets))
        return self.c_signal * (scores - mu) / sd


class EqualWeightSignal(PortfolioSignal):
    """
    Flat signal — all assets get the same expected return.
    """

    def compute(self, close: pd.DataFrame, date: pd.Timestamp, assets: List[str]) -> np.ndarray:
        return np.zeros(len(assets))
