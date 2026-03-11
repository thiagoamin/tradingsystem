"""
research/signals.py
====================
Signals estimate (expected_return μ, volatility σ) from price history.

These estimates are fed into a UtilityFunction to produce a scalar score.
The score drives the strategy's buy / sell decision.

  Signal.estimate() → (μ, σ)  →  UtilityFunction.evaluate(μ, σ)  →  score

To add a new signal: subclass Signal and implement estimate().
"""

from __future__ import annotations

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from abc import ABC, abstractmethod
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from backtest_lab import SimplePortfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rolling_vol(closes: List[float], window: int) -> float:
    """Return daily return volatility (std dev) over the last ``window`` bars.

    Args:
        closes: Full price history; only the trailing ``window`` values are used.
        window: Number of bars to include in the volatility estimate.

    Returns:
        Population standard deviation of daily returns, or ``0.01`` when fewer
        than two data points are available.
    """
    n = min(window, len(closes))
    if n < 2:
        return 0.01  # fallback: 1 % daily vol
    rets = [(closes[-n + i] - closes[-n + i - 1]) / closes[-n + i - 1]
            for i in range(1, n)]
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(variance) if variance > 0 else 0.01


def _rolling_mean(closes: List[float], window: int) -> float:
    """Return the simple moving average of the last ``window`` closes.

    Args:
        closes: Full price history.
        window: Look-back period; capped at ``len(closes)``.

    Returns:
        Arithmetic mean of the trailing ``window`` close prices.
    """
    n = min(window, len(closes))
    return sum(closes[-n:]) / n


# ---------------------------------------------------------------------------
# Signal interface
# ---------------------------------------------------------------------------

class Signal(ABC):
    """Estimates (expected_daily_return, daily_volatility) from price history.

    Both outputs should be in return-space (e.g. 0.01 = 1 % daily return).
    The sign of expected_return encodes direction:
      positive → bullish (entry attractive)
      negative → bearish (exit attractive)
    """

    name: str = "unnamed"

    @abstractmethod
    def estimate(
        self,
        closes: List[float],
        portfolio: "SimplePortfolio",
        price: float,
    ) -> Tuple[float, float]:
        """Estimate expected return and volatility for the current bar.

        Args:
            closes: Full close-price history up to and including the current bar.
            portfolio: Current portfolio state (position size, average cost).
            price: Current bar's close price.

        Returns:
            A ``(expected_return, volatility)`` tuple, both expressed as daily
            return fractions (e.g. ``0.01`` = 1 %).
        """
        ...

    def reset(self) -> None:
        """Reset any internal state before a new backtest run.

        Override if the signal holds state between bars (e.g. a running
        maximum).  The default implementation is a no-op.
        """


# ---------------------------------------------------------------------------
# Concrete signals
# ---------------------------------------------------------------------------

class DipSignal(Signal):
    """Estimates a positive expected return when price drops more than ``drop_pct``.

    Based on the mean-reversion hypothesis that dips tend to recover.
    Expected return = dip magnitude / reversion_window (spread over N bars).
    Emits a negative expected return when the position exceeds ``profit_target``,
    which the strategy interprets as an exit signal.
    """

    def __init__(
        self,
        drop_pct: float = 0.02,
        profit_target_pct: float = 0.05,
        reversion_window: int = 5,
        vol_window: int = 20,
    ):
        """Initialise the dip signal.

        Args:
            drop_pct: Minimum single-bar decline (as a positive fraction) that
                triggers an entry signal.
            profit_target_pct: Unrealised gain fraction at which an exit signal
                is emitted.
            reversion_window: Number of bars over which the expected recovery is
                amortised, reducing the per-bar mu estimate.
            vol_window: Look-back period for rolling volatility.
        """
        self.drop_pct = drop_pct
        self.profit_target_pct = profit_target_pct
        self.reversion_window = reversion_window
        self.vol_window = vol_window
        self.name = f"Dip({drop_pct:.0%}→{profit_target_pct:.0%})"

    def estimate(self, closes, portfolio, price):
        """Return ``(mu, sigma)`` based on dip detection and profit-target logic.

        Args:
            closes: Close-price history up to the current bar.
            portfolio: Current portfolio state.
            price: Current close price.

        Returns:
            ``(expected_return, volatility)`` tuple; ``expected_return`` is
            positive on a dip entry, negative when the profit target is reached,
            and zero otherwise.
        """
        sigma = _rolling_vol(closes, self.vol_window)

        # Exit signal: holding and profit target reached
        if portfolio.position > 0 and portfolio.avg_cost > 0:
            gain = (price - portfolio.avg_cost) / portfolio.avg_cost
            if gain >= self.profit_target_pct:
                return (-self.profit_target_pct, sigma)

        # Entry signal: dip detected — expected return from mean reversion
        if len(closes) >= 2:
            daily_ret = (closes[-1] - closes[-2]) / closes[-2]
            if daily_ret <= -self.drop_pct:
                mu = abs(daily_ret) / self.reversion_window
                return (mu, sigma)

        return (0.0, sigma)


class MomentumSignal(Signal):
    """Estimates expected return from the spread between a short and long MA.

    When the short MA is above the long MA, the trend is up and the stock is
    expected to continue rising.  The spread size (normalised by the long MA)
    is used as the expected-return estimate.  Emits a negative expected return
    when holding and the trend reverses, which acts as an exit signal.
    """

    def __init__(self, short: int = 20, long: int = 50, vol_window: int = 20):
        """Initialise the momentum signal.

        Args:
            short: Look-back period for the fast moving average.
            long: Look-back period for the slow moving average.
            vol_window: Look-back period for rolling volatility.
        """
        self.short = short
        self.long = long
        self.vol_window = vol_window
        self.name = f"Momentum({short}/{long})"

    def estimate(self, closes, portfolio, price):
        """Return ``(mu, sigma)`` based on the short/long MA spread.

        Args:
            closes: Close-price history up to the current bar.
            portfolio: Current portfolio state.
            price: Current close price (unused directly; supplied for interface
                compatibility).

        Returns:
            ``(expected_return, volatility)`` tuple; returns ``(0.0, sigma)``
            when fewer than ``long`` bars are available.
        """
        sigma = _rolling_vol(closes, self.vol_window)
        if len(closes) < self.long:
            return (0.0, sigma)

        ma_s = _rolling_mean(closes, self.short)
        ma_l = _rolling_mean(closes, self.long)

        # Normalised spread → proxy for expected daily drift
        spread = (ma_s - ma_l) / ma_l
        mu = spread / self.long  # amortise spread over the lookback period

        # If holding and trend has reversed, return negative mu → exit
        if portfolio.position > 0 and spread < 0:
            return (-abs(mu), sigma)

        return (mu, sigma)


class MeanReversionSignal(Signal):
    """Estimates expected return from the z-score of price relative to its rolling mean.

    Based on the Ornstein-Uhlenbeck mean-reversion hypothesis.
    Price far below the rolling mean → large positive expected return.
    Price far above the rolling mean → large negative expected return.
    """

    def __init__(self, window: int = 20):
        """Initialise the mean-reversion signal.

        Args:
            window: Look-back period for both the rolling mean/std and
                rolling volatility.
        """
        self.window = window
        self.name = f"MeanRev(w={window})"

    def estimate(self, closes, portfolio, price):
        """Return ``(mu, sigma)`` derived from the current price z-score.

        Args:
            closes: Close-price history up to the current bar.
            portfolio: Current portfolio state (unused; supplied for interface
                compatibility).
            price: Current close price used to compute the z-score.

        Returns:
            ``(expected_return, volatility)`` tuple; returns ``(0.0, sigma)``
            when fewer than ``window`` bars are available or price std is zero.
        """
        sigma = _rolling_vol(closes, self.window)
        if len(closes) < self.window:
            return (0.0, sigma)

        w = closes[-self.window:]
        mean = sum(w) / len(w)
        std_price = math.sqrt(sum((c - mean) ** 2 for c in w) / len(w))
        if std_price == 0:
            return (0.0, sigma)

        z = (price - mean) / std_price  # +2 = 2σ above mean
        # Expected return: price moves back toward mean over ~window/2 bars
        mu = -z * sigma / (self.window / 2)
        return (mu, sigma)
