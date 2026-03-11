#!/usr/bin/env python
"""
research/backtest_lab.py
========================
Lightweight strategy research framework.

Architecture
------------

  Signal  (signals.py)
      ↓  estimate(closes, portfolio, price) → (μ, σ)
  UtilityFunction  (allocation/utility_functions.py)
      ↓  evaluate(μ, σ) → score    ← risk_aversion lives here
  SignalDrivenStrategy
      ↓  buy if score ≥ buy_threshold, sell if score ≤ sell_threshold

The risk_aversion coefficient in the utility function controls how much
variance is penalised.  The same signal with different risk_aversion values
will produce different trade frequency and sizing behaviour — this is the
main thing to experiment with.

Usage (requires TWS / IB Gateway running on port 7497):
    python research/backtest_lab.py
"""

from __future__ import annotations

import argparse
import copy
import math
import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from allocation.utility_functions import (
    ExponentialUtility,
    LogUtility,
    MeanVarianceUtility,
    UtilityFunction,
)
from fetchers.base import ProviderError
from fetchers.models import BarInterval, OHLCVBar
from fetchers.providers.ibkr import IBKRHistoricalFetcher
from research.signals import DipSignal, MeanReversionSignal, MomentumSignal, Signal


# ---------------------------------------------------------------------------
# Lightweight portfolio  (no engine dependency)
# ---------------------------------------------------------------------------

@dataclass
class SimplePortfolio:
    """Minimal portfolio for research backtests with no engine dependency.

    Attributes:
        cash: Available cash balance.
        position: Number of shares currently held (long only).
        avg_cost: Average cost basis per share of the current position.
        n_trades: Total number of buy and sell transactions executed.
    """

    cash: float
    position: int = 0
    avg_cost: float = 0.0
    n_trades: int = 0

    def buy(self, qty: int, price: float) -> None:
        """Add shares to the position at the given price.

        Args:
            qty: Number of shares to buy.
            price: Execution price per share.
        """
        total_cost = self.avg_cost * self.position + price * qty
        self.position += qty
        self.avg_cost = total_cost / self.position
        self.cash -= qty * price
        self.n_trades += 1

    def sell(self, qty: int, price: float) -> None:
        """Remove shares from the position at the given price.

        Args:
            qty: Number of shares to sell.
            price: Execution price per share.
        """
        self.position -= qty
        if self.position == 0:
            self.avg_cost = 0.0
        self.cash += qty * price
        self.n_trades += 1

    def equity(self, price: float) -> float:
        """Return total portfolio value (cash + mark-to-market position).

        Args:
            price: Current market price used to value the position.

        Returns:
            Total equity in dollars.
        """
        return self.cash + self.position * price

    def max_shares(self, price: float) -> int:
        """Return the maximum number of shares purchasable with available cash.

        Args:
            price: Current market price per share.

        Returns:
            Largest integer share count affordable at ``price``.
        """
        return int(self.cash // price)


@dataclass
class MultiAssetPortfolio:
    """Shared-cash portfolio across multiple symbols."""

    cash: float
    positions: Dict[str, int]
    avg_costs: Dict[str, float]
    n_trades: int = 0

    def __init__(self, cash: float):
        self.cash = cash
        self.positions = {}
        self.avg_costs = {}
        self.n_trades = 0

    def position(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def avg_cost(self, symbol: str) -> float:
        return self.avg_costs.get(symbol, 0.0)

    def max_shares(self, price: float) -> int:
        return int(self.cash // price)

    def buy(self, symbol: str, qty: int, price: float) -> None:
        if qty <= 0:
            return
        current_qty = self.position(symbol)
        current_cost = self.avg_cost(symbol)
        new_qty = current_qty + qty
        self.avg_costs[symbol] = (
            (current_cost * current_qty + price * qty) / new_qty
            if new_qty > 0
            else 0.0
        )
        self.positions[symbol] = new_qty
        self.cash -= qty * price
        self.n_trades += 1

    def sell(self, symbol: str, qty: int, price: float) -> None:
        if qty <= 0:
            return
        current_qty = self.position(symbol)
        new_qty = current_qty - qty
        if new_qty <= 0:
            self.positions.pop(symbol, None)
            self.avg_costs.pop(symbol, None)
        else:
            self.positions[symbol] = new_qty
        self.cash += qty * price
        self.n_trades += 1

    def equity(self, latest_prices: Dict[str, float]) -> float:
        total = self.cash
        for symbol, qty in self.positions.items():
            total += qty * latest_prices.get(symbol, 0.0)
        return total


class _SymbolPortfolioView:
    """Per-symbol view into a shared multi-asset portfolio."""

    def __init__(self, portfolio: MultiAssetPortfolio, symbol: str):
        self._portfolio = portfolio
        self._symbol = symbol

    @property
    def position(self) -> int:
        return self._portfolio.position(self._symbol)

    @property
    def avg_cost(self) -> float:
        return self._portfolio.avg_cost(self._symbol)

    def max_shares(self, price: float) -> int:
        return self._portfolio.max_shares(price)

    def buy(self, qty: int, price: float) -> None:
        self._portfolio.buy(self._symbol, qty, price)

    def sell(self, qty: int, price: float) -> None:
        self._portfolio.sell(self._symbol, qty, price)


# ---------------------------------------------------------------------------
# Strategy interface
# ---------------------------------------------------------------------------

class Strategy(ABC):
    """Abstract base class for bar-by-bar trading strategies.

    Attributes:
        name: Human-readable identifier used in results tables.
    """

    name: str = "unnamed"

    @abstractmethod
    def decide(
        self,
        closes: List[float],
        portfolio: SimplePortfolio,
        price: float,
    ) -> Optional[Tuple[str, int]]:
        """Decide what action to take on the current bar.

        Args:
            closes: Full close-price history up to and including the current bar.
            portfolio: Current portfolio state.
            price: Current bar's close price.

        Returns:
            ``("buy", qty)``, ``("sell", qty)``, or ``None`` for no action.
        """
        ...

    def reset(self) -> None:
        """Reset any internal state before a new backtest run."""


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

class BuyAndHold(Strategy):
    """Buy maximum shares on bar 1, never sell.  Baseline benchmark."""

    name = "BuyAndHold"

    def decide(self, closes, portfolio, price):
        """Buy maximum affordable shares on the first bar; hold forever.

        Args:
            closes: Close-price history (length checked implicitly via position).
            portfolio: Current portfolio state.
            price: Current close price.

        Returns:
            ``("buy", qty)`` on the first bar when flat, otherwise ``None``.
        """
        if portfolio.position == 0:
            qty = portfolio.max_shares(price)
            return ("buy", qty) if qty > 0 else None
        return None


class SignalDrivenStrategy(Strategy):
    """Connects a Signal to a UtilityFunction to produce buy/sell decisions.

    Flow each bar:
      1. Signal estimates (μ, σ) from price history.
      2. UtilityFunction scores the (μ, σ) pair using its risk_aversion.
      3. Buy  if score ≥ buy_threshold  and flat.
      4. Sell if score ≤ sell_threshold and long.

    Changing the UtilityFunction's risk_aversion changes how aggressively
    the strategy acts on the same signal — no other code needs to change.
    """

    def __init__(
        self,
        signal: Signal,
        utility: UtilityFunction,
        buy_threshold: float = 0.0,
        sell_threshold: float = 0.0,
        buy_shares: int | str = "max",
    ):
        """Initialise the signal-driven strategy.

        Args:
            signal: Signal that produces ``(mu, sigma)`` estimates.
            utility: Utility function that converts ``(mu, sigma)`` to a score.
            buy_threshold: Minimum score required to open a long position.
            sell_threshold: Maximum score at which an existing long is closed.
            buy_shares: Fixed share count per buy order, or ``"max"`` to spend
                all available cash.
        """
        self.signal = signal
        self.utility = utility
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.buy_shares = buy_shares
        self.name = f"{signal.name}  [{utility.name}]"

    def reset(self) -> None:
        """Delegate state reset to the underlying signal."""
        self.signal.reset()

    def decide(self, closes, portfolio, price):
        """Evaluate the signal and utility, then return a buy, sell, or hold.

        Args:
            closes: Close-price history up to the current bar.
            portfolio: Current portfolio state.
            price: Current close price.

        Returns:
            ``("buy", qty)`` when the score exceeds ``buy_threshold`` and the
            portfolio is flat; ``("sell", position)`` when the score is below
            ``sell_threshold`` and a position is held; ``None`` otherwise.
        """
        mu, sigma = self.signal.estimate(closes, portfolio, price)
        score = self.utility.evaluate(mu, sigma)

        if score >= self.buy_threshold and portfolio.position == 0:
            qty = (
                portfolio.max_shares(price)
                if self.buy_shares == "max"
                else min(int(self.buy_shares), portfolio.max_shares(price))
            )
            return ("buy", qty) if qty > 0 else None

        if score <= self.sell_threshold and portfolio.position > 0:
            return ("sell", portfolio.position)

        return None


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Immutable record of a single strategy/symbol backtest run.

    Attributes:
        strategy_name: Display name of the strategy that produced this result.
        symbol: Ticker symbol the strategy was run against.
        equity_curve: Portfolio equity value recorded after each bar.
        timestamps: Bar timestamps corresponding to each equity_curve entry.
        initial_cash: Starting cash balance used to compute returns.
        n_trades: Total number of buy and sell executions.
    """

    strategy_name: str
    symbol: str
    equity_curve: List[float]
    timestamps: List[datetime]
    initial_cash: float
    n_trades: int

    @property
    def total_return(self) -> float:
        """Total return over the full backtest period as a fraction.

        Returns:
            ``(final_equity - initial_cash) / initial_cash``, or ``0.0`` when
            the equity curve is empty.
        """
        if not self.equity_curve:
            return 0.0
        return (self.equity_curve[-1] - self.initial_cash) / self.initial_cash

    @property
    def annualized_return(self) -> float:
        """Compound annualised return assuming 252 trading days per year.

        Returns:
            Annualised return as a fraction, or ``0.0`` when fewer than two
            bars are available.
        """
        n = len(self.equity_curve)
        if n < 2:
            return 0.0
        return (1 + self.total_return) ** (252 / n) - 1

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown over the equity curve.

        Returns:
            Largest fractional decline from any peak, as a positive number
            (e.g. ``0.15`` = 15 % drawdown).
        """
        peak, worst = self.initial_cash, 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            worst = max(worst, (peak - eq) / peak)
        return worst

    @property
    def sharpe(self) -> float:
        """Annualised Sharpe ratio computed from daily equity returns.

        Returns:
            Sharpe ratio (assuming zero risk-free rate), or ``0.0`` when fewer
            than two bars are present or daily return std dev is zero.
        """
        if len(self.equity_curve) < 2:
            return 0.0
        rets = [
            (self.equity_curve[i] - self.equity_curve[i - 1]) / self.equity_curve[i - 1]
            for i in range(1, len(self.equity_curve))
        ]
        mean = sum(rets) / len(rets)
        std = math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets))
        return (mean / std * math.sqrt(252)) if std > 0 else 0.0


@dataclass
class PortfolioBacktestResult:
    """Result of a true multi-asset (shared-cash) strategy run."""

    strategy_name: str
    symbols: List[str]
    equity_curve: List[float]
    timestamps: List[datetime]
    initial_cash: float
    n_trades: int

    @property
    def total_return(self) -> float:
        if not self.equity_curve:
            return 0.0
        return (self.equity_curve[-1] - self.initial_cash) / self.initial_cash

    @property
    def annualized_return(self) -> float:
        n = len(self.equity_curve)
        if n < 2:
            return 0.0
        return (1 + self.total_return) ** (252 / n) - 1

    @property
    def max_drawdown(self) -> float:
        peak, worst = self.initial_cash, 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            worst = max(worst, (peak - eq) / peak)
        return worst

    @property
    def sharpe(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        rets = [
            (self.equity_curve[i] - self.equity_curve[i - 1]) / self.equity_curve[i - 1]
            for i in range(1, len(self.equity_curve))
        ]
        mean = sum(rets) / len(rets)
        std = math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets))
        return (mean / std * math.sqrt(252)) if std > 0 else 0.0


def run_backtest(
    strategy: Strategy,
    bars: List[OHLCVBar],
    initial_cash: float = 10_000.0,
) -> BacktestResult:
    """Replay OHLCV bars through a strategy and return performance metrics.

    The strategy is reset before the loop begins.  Each bar's close price is
    appended to the running history before ``decide`` is called so signals
    always see the current bar's close.  Order validation is applied:
    buy quantities are capped at ``max_shares`` and sell quantities are capped
    at the current position.

    Args:
        strategy: Strategy instance to evaluate.
        bars: Chronologically ordered OHLCV bars for a single symbol.
        initial_cash: Starting cash balance for the paper portfolio.

    Returns:
        A ``BacktestResult`` containing the equity curve, timestamps, and
        summary statistics for the run.
    """
    strategy.reset()
    portfolio = SimplePortfolio(cash=initial_cash)
    closes: List[float] = []
    equity_curve: List[float] = []
    timestamps: List[datetime] = []

    for bar in bars:
        closes.append(bar.close)
        action = strategy.decide(closes, portfolio, bar.close)
        if action:
            side, qty = action
            if side == "buy" and 0 < qty <= portfolio.max_shares(bar.close):
                portfolio.buy(qty, bar.close)
            elif side == "sell" and 0 < qty <= portfolio.position:
                portfolio.sell(qty, bar.close)
        equity_curve.append(portfolio.equity(bar.close))
        timestamps.append(bar.ts)

    return BacktestResult(
        strategy_name=strategy.name,
        symbol=bars[0].symbol if bars else "?",
        equity_curve=equity_curve,
        timestamps=timestamps,
        initial_cash=initial_cash,
        n_trades=portfolio.n_trades,
    )


def run_multi_asset_backtest(
    strategy_template: Strategy,
    bars_by_symbol: Dict[str, List[OHLCVBar]],
    initial_cash: float = 10_000.0,
) -> PortfolioBacktestResult:
    """Run a true multi-asset backtest with shared cash and positions."""
    symbols = sorted(sym for sym, bars in bars_by_symbol.items() if bars)
    if not symbols:
        return PortfolioBacktestResult(
            strategy_name=strategy_template.name,
            symbols=[],
            equity_curve=[],
            timestamps=[],
            initial_cash=initial_cash,
            n_trades=0,
        )

    # Clone strategy per symbol so stateful signals do not leak across assets.
    per_symbol_strategy: Dict[str, Strategy] = {}
    for symbol in symbols:
        strategy = copy.deepcopy(strategy_template)
        strategy.reset()
        per_symbol_strategy[symbol] = strategy

    bars_by_ts: Dict[datetime, List[OHLCVBar]] = {}
    for symbol in symbols:
        for bar in bars_by_symbol[symbol]:
            bars_by_ts.setdefault(bar.ts, []).append(bar)

    portfolio = MultiAssetPortfolio(cash=initial_cash)
    closes_by_symbol: Dict[str, List[float]] = {symbol: [] for symbol in symbols}
    latest_prices: Dict[str, float] = {}
    equity_curve: List[float] = []
    timestamps: List[datetime] = []

    for ts in sorted(bars_by_ts):
        for bar in sorted(bars_by_ts[ts], key=lambda b: b.symbol):
            symbol = bar.symbol
            closes = closes_by_symbol[symbol]
            closes.append(bar.close)
            latest_prices[symbol] = bar.close

            strategy = per_symbol_strategy[symbol]
            view = _SymbolPortfolioView(portfolio, symbol)
            action = strategy.decide(closes, view, bar.close)
            if not action:
                continue

            side, qty = action
            if side == "buy" and 0 < qty <= view.max_shares(bar.close):
                view.buy(qty, bar.close)
            elif side == "sell" and 0 < qty <= view.position:
                view.sell(qty, bar.close)

        equity_curve.append(portfolio.equity(latest_prices))
        timestamps.append(ts)

    return PortfolioBacktestResult(
        strategy_name=strategy_template.name,
        symbols=symbols,
        equity_curve=equity_curve,
        timestamps=timestamps,
        initial_cash=initial_cash,
        n_trades=portfolio.n_trades,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results_table(results: List[BacktestResult]) -> None:
    """Print a formatted performance table grouped by symbol, sorted by return.

    Results are grouped by symbol and sorted descending by total return within
    each group.  Columns: strategy name, total return, annualised return,
    max drawdown, Sharpe ratio, and trade count.

    Args:
        results: List of backtest results to display; may span multiple symbols.
    """
    col_w = [46, 10, 10, 10, 8, 8]
    headers = ["Strategy  [Utility]", "Return", "Ann.Ret", "MaxDD", "Sharpe", "Trades"]
    sep = "-" * (sum(col_w) + 2 * (len(col_w) - 1))

    def row(*cells):
        """Format a single table row by left-justifying each cell to its column width."""
        return "  ".join(str(c).ljust(w) for c, w in zip(cells, col_w))

    last_sym = None
    for r in sorted(results, key=lambda x: (x.symbol, -x.total_return)):
        if r.symbol != last_sym:
            print(f"\n  ── {r.symbol} ──")
            print(sep)
            print(row(*headers))
            print(sep)
            last_sym = r.symbol
        print(row(
            f"  {r.strategy_name}",
            f"{r.total_return:+.1%}",
            f"{r.annualized_return:+.1%}",
            f"{-r.max_drawdown:.1%}",
            f"{r.sharpe:.2f}",
            str(r.n_trades),
        ))
    print()


def print_portfolio_results_table(results: List[PortfolioBacktestResult]) -> None:
    """Print one row per strategy for multi-asset shared-cash backtests."""
    if not results:
        return

    print("\nMulti-Asset Portfolio Results")
    print("-" * 102)
    print(
        f"{'Strategy  [Utility]':46}  {'Assets':>6}  {'Return':>8}  {'Ann.Ret':>8}  "
        f"{'MaxDD':>8}  {'Sharpe':>8}  {'Trades':>6}"
    )
    print("-" * 102)
    for result in sorted(results, key=lambda r: r.total_return, reverse=True):
        print(
            f"{result.strategy_name[:46]:46}  {len(result.symbols):6d}  "
            f"{result.total_return:+8.1%}  {result.annualized_return:+8.1%}  "
            f"{-result.max_drawdown:8.1%}  {result.sharpe:8.2f}  {result.n_trades:6d}"
        )
    print("-" * 102)


# ---------------------------------------------------------------------------
# Experiment config — edit this section to run your own experiments
# ---------------------------------------------------------------------------

UNIVERSES: Dict[str, List[str]] = {
    # Default broad basket for utility/portfolio testing across sectors.
    "diversified": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
        "JPM", "XOM", "UNH", "LLY", "SPY", "QQQ",
    ],
    "megacap": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"],
    "etf_core": ["SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV"],
}
START   = datetime(2024, 1, 1, tzinfo=timezone.utc)
END     = datetime(2024, 12, 31, tzinfo=timezone.utc)
CASH    = 10_000.0

STRATEGIES: List[Strategy] = [
    # ── Baseline ────────────────────────────────────────────────────────────
    BuyAndHold(),

    # ── Same Dip signal, three different risk aversions ─────────────────────
    # λ=0.5 is more aggressive (less variance penalty) than λ=2.0
    SignalDrivenStrategy(DipSignal(0.02, 0.05), MeanVarianceUtility(risk_aversion=0.5),
                         buy_threshold=0.001, sell_threshold=-0.001, buy_shares=10),
    SignalDrivenStrategy(DipSignal(0.02, 0.05), MeanVarianceUtility(risk_aversion=2.0),
                         buy_threshold=0.001, sell_threshold=-0.001, buy_shares=10),
    SignalDrivenStrategy(DipSignal(0.02, 0.05), LogUtility(risk_aversion=1.0),
                         buy_threshold=0.001, sell_threshold=-0.001, buy_shares=10),

    # ── Momentum signal with different utility functions ─────────────────────
    SignalDrivenStrategy(MomentumSignal(20, 50), MeanVarianceUtility(risk_aversion=1.0),
                         buy_threshold=0.000_05, sell_threshold=-0.000_05),
    SignalDrivenStrategy(MomentumSignal(10, 30), ExponentialUtility(risk_aversion=50),
                         buy_threshold=0.000_05, sell_threshold=-0.000_05),

    # ── Mean reversion ───────────────────────────────────────────────────────
    SignalDrivenStrategy(MeanReversionSignal(20), MeanVarianceUtility(risk_aversion=1.0),
                         buy_threshold=0.000_1, sell_threshold=-0.000_1),
]


def print_strategy_summary(results: List[BacktestResult]) -> None:
    """Print per-strategy averages across all symbols."""
    grouped: Dict[str, List[BacktestResult]] = {}
    for result in results:
        grouped.setdefault(result.strategy_name, []).append(result)

    if not grouped:
        return

    print("\nStrategy Summary Across Symbols")
    print("-" * 90)
    print(f"{'Strategy':46}  {'AvgRet':>8}  {'AvgAnn':>8}  {'AvgDD':>8}  {'AvgSharpe':>9}  {'Trades':>6}")
    print("-" * 90)
    for name, runs in sorted(grouped.items(), key=lambda item: -sum(r.total_return for r in item[1]) / len(item[1])):
        n = len(runs)
        avg_ret = sum(r.total_return for r in runs) / n
        avg_ann = sum(r.annualized_return for r in runs) / n
        avg_dd = sum(r.max_drawdown for r in runs) / n
        avg_sharpe = sum(r.sharpe for r in runs) / n
        total_trades = sum(r.n_trades for r in runs)
        print(
            f"{name[:46]:46}  {avg_ret:+8.1%}  {avg_ann:+8.1%}  {-avg_dd:8.1%}  {avg_sharpe:9.2f}  {total_trades:6d}"
        )
    print("-" * 90)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run utility-driven research backtests with IBKR data.")
    parser.add_argument("--universe", choices=sorted(UNIVERSES.keys()), default="diversified")
    parser.add_argument("--symbols", nargs="+", metavar="SYM", help="Optional explicit symbol list (overrides --universe).")
    parser.add_argument(
        "--mode",
        choices=["portfolio", "per_symbol"],
        default="portfolio",
        help="portfolio = shared cash across all symbols (true multi-asset).",
    )
    parser.add_argument("--start", default=START.date().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--end", default=END.date().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=CASH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497, help="TWS paper default=7497, Gateway paper default=4002")
    parser.add_argument("--client-id", type=int, default=11)
    parser.add_argument("--timeout-sec", type=float, default=45.0, help="IBKR request timeout per API call.")
    parser.add_argument("--retries", type=int, default=2, help="Retries per symbol when historical request times out.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    selected = args.symbols if args.symbols else UNIVERSES[args.universe]
    symbols = list(dict.fromkeys(sym.strip().upper() for sym in selected if sym and sym.strip()))
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)

    print(f"Fetching daily bars: {symbols}  {start.date()} → {end.date()}")
    print(
        "IBKR connection: "
        f"host={args.host} port={args.port} client_id={args.client_id} "
        f"timeout={args.timeout_sec}s retries={args.retries}\n"
    )

    fetcher = IBKRHistoricalFetcher(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        timeout_sec=args.timeout_sec,
    )
    bars_by_symbol: Dict[str, List[OHLCVBar]] = {}
    try:
        for sym in symbols:
            bars: List[OHLCVBar] = []
            last_exc: Optional[ProviderError] = None
            attempts = max(1, args.retries + 1)
            for attempt in range(1, attempts + 1):
                try:
                    bars = fetcher.get_ohlcv_bars([sym], start, end, BarInterval.DAY_1)
                    last_exc = None
                    break
                except ProviderError as exc:
                    last_exc = exc
                    is_timeout = "timeout waiting for historical bars" in str(exc)
                    if not is_timeout or attempt == attempts:
                        break
                    wait_s = min(8, 2 * attempt)
                    print(
                        f"  {sym}: attempt {attempt}/{attempts} timed out; "
                        f"retrying in {wait_s}s..."
                    )
                    time.sleep(wait_s)

            if last_exc is not None:
                raise last_exc

            bars_by_symbol[sym] = bars
            if bars:
                print(f"  {sym}: {len(bars)} bars  ({bars[0].ts.date()} → {bars[-1].ts.date()})")
            else:
                print(f"  {sym}: no data")
    except ProviderError as exc:
        print(f"\nIBKR connection/data error: {exc}")
        print("Check TWS/IB Gateway is running, API is enabled, and the host/port match.")
        print("Common paper ports: TWS=7497, IB Gateway=4002.")
        if "timeout waiting for historical bars" in str(exc):
            print(
                "This usually means IBKR accepted the socket but did not return data fast enough.\n"
                "Try a larger timeout (e.g. --timeout-sec 90), fewer symbols, or rerun after TWS data farms warm up."
            )
        raise SystemExit(1) from exc
    finally:
        fetcher.close()

    if args.mode == "portfolio":
        portfolio_results: List[PortfolioBacktestResult] = []
        for strategy in STRATEGIES:
            portfolio_results.append(
                run_multi_asset_backtest(strategy, bars_by_symbol, initial_cash=args.cash)
            )

        print(f"\nPortfolio Results  (shared cash ${args.cash:,.0f}, one strategy across all symbols)")
        print_portfolio_results_table(portfolio_results)
    else:
        all_results: List[BacktestResult] = []
        for sym, bars in bars_by_symbol.items():
            if not bars:
                continue
            for strategy in STRATEGIES:
                all_results.append(run_backtest(strategy, bars, initial_cash=args.cash))

        print(f"\nResults  (initial cash ${args.cash:,.0f} per strategy/symbol)")
        print_results_table(all_results)
        print_strategy_summary(all_results)
