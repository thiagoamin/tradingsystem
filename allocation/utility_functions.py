"""
Utility functions over (expected_return, volatility).

A utility function scores a position's risk/reward tradeoff.
Higher score = more attractive. The risk_aversion coefficient controls
how strongly variance is penalized relative to expected return.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod


class UtilityFunction(ABC):
    """Scores a (mu, sigma) pair produced by a signal/forecast model."""

    name: str = "unnamed"
    risk_aversion: float = 1.0

    @abstractmethod
    def evaluate(self, expected_return: float, volatility: float) -> float:
        """Return scalar utility score. Positive is favorable for allocation."""
        ...


class MeanVarianceUtility(UtilityFunction):
    """Classic Markowitz utility: U = mu - (lambda/2) * sigma^2."""

    def __init__(self, risk_aversion: float = 1.0):
        self.risk_aversion = risk_aversion
        self.name = f"MeanVar(lambda={risk_aversion})"

    def evaluate(self, expected_return: float, volatility: float) -> float:
        return expected_return - (self.risk_aversion / 2.0) * (volatility ** 2)


class LogUtility(UtilityFunction):
    """Log-wealth utility with additional variance penalty."""

    def __init__(self, risk_aversion: float = 1.0):
        self.risk_aversion = risk_aversion
        self.name = f"Log(lambda={risk_aversion})"

    def evaluate(self, expected_return: float, volatility: float) -> float:
        adjusted = 1.0 + expected_return
        if adjusted <= 0:
            return -float("inf")
        return math.log(adjusted) - (self.risk_aversion / 2.0) * (volatility ** 2)


class ExponentialUtility(UtilityFunction):
    """CARA utility: U = (1 - exp(-lambda * mu))/lambda - (lambda/2) * sigma^2."""

    def __init__(self, risk_aversion: float = 1.0):
        self.risk_aversion = risk_aversion
        self.name = f"Exp(lambda={risk_aversion})"

    def evaluate(self, expected_return: float, volatility: float) -> float:
        lam = self.risk_aversion
        if lam == 0:
            return expected_return
        certainty_equiv = (1.0 - math.exp(-lam * expected_return)) / lam
        return certainty_equiv - (lam / 2.0) * (volatility ** 2)
