"""
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np
import pandas as pd


class RegimeDetector(ABC):
    @abstractmethod
    def detect(self, close: pd.DataFrame, date: pd.Timestamp, sigma: np.ndarray, assets: List[str]) -> str:
        """
        Classify the current regime.

        Returns: a regime label string (``"risk-on"``, ``"neutral"``, ``"risk-off"``).
        """
        ...


class MACorrelationDetector(RegimeDetector):
    """
    Regime from two filters:
        1. Trend: ``trend_asset`` price vs its ``ma_window``-day moving average.
        2. Crowding: average pairwise correlation derived from ``sigma``.

    Decision table:
        trend_above AND avg_corr < lo       = "risk-on"
        (not trend_above) OR avg_corr > hi  = "risk-off"
        otherwise                           = "neutral"
    """

    def __init__(self, corr_thresh_lo: float = 0.40, corr_thresh_hi: float = 0.60, 
                 ma_window: int = 200, trend_asset: str = "SPY"):
        self.corr_thresh_lo = corr_thresh_lo
        self.corr_thresh_hi = corr_thresh_hi
        self.ma_window = ma_window
        self.trend_asset = trend_asset

    def detect(self, close: pd.DataFrame, date: pd.Timestamp, sigma: np.ndarray, assets: List[str]) -> str:
        loc = close.index.get_loc(date)
        prices = close[self.trend_asset].values
        ma = prices[max(0, loc - self.ma_window + 1) : loc + 1].mean()
        trend_above = prices[loc] > ma

        n = sigma.shape[0]
        std = np.sqrt(np.diag(sigma))
        corr = sigma / np.outer(std, std)
        np.fill_diagonal(corr, 0.0)
        avg_corr = corr.sum() / (n * (n - 1))

        if trend_above and avg_corr < self.corr_thresh_lo:
            return "risk-on"
        if (not trend_above) or avg_corr > self.corr_thresh_hi:
            return "risk-off"
        return "neutral"


class NoRegime(RegimeDetector):
    """
    Always returns "neutral"
    """

    def detect(self, close: pd.DataFrame, date: pd.Timestamp, sigma: np.ndarray, assets: List[str]) -> str:
        return "neutral"
