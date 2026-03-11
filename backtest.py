#!/usr/bin/env python
"""
Backtest runner — replay historical IBKR bars through the trading system.

Usage:
    python backtest.py
    python backtest.py --symbols AAPL MSFT --start 2024-01-01 --end 2024-12-31
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from allocation import MeanVarianceUtility, UtilityAllocator
from data.feature_engine import FeatureEngine
from engine.bus import EventBus
from engine.engine import SignalEngine
from engine.execution import PaperExecution
from engine.portfolio import Portfolio
from engine.risk import BasicRiskManager
from engine.rules import PercentDropRule
from engine.sinks import ConsoleSink, EventSink, LogSink
from engine.state import MarketState
from engine.strategy import Strategy
from engine.strategies.basic import BuyDipStrategy
from engine.strategies.utility_allocation import UtilityAllocationStrategy
from engine.system import TradingSystem
from fetchers.models import BarInterval
from fetchers.providers.ibkr import IBKRHistoricalFetcher


def _build_strategy(
    strategy_name: str,
    shares_per_trade: int,
    profit_target_pct: float,
    risk_aversion: float,
    max_weight: float,
    cash_buffer: float,
) -> Strategy:
    if strategy_name == "utility":
        return UtilityAllocationStrategy(
            allocator=UtilityAllocator(
                utility=MeanVarianceUtility(risk_aversion=risk_aversion),
                max_weight=max_weight,
                cash_buffer=cash_buffer,
            )
        )
    if strategy_name == "buy_dip":
        return BuyDipStrategy(
            shares_per_trade=shares_per_trade,
            profit_target_pct=profit_target_pct,
        )
    raise ValueError(f"unknown strategy: {strategy_name}")


def run_backtest(
    symbols: List[str],
    start: datetime,
    end: datetime,
    initial_cash: float = 100_000.0,
    drop_threshold: float = -0.02,
    shares_per_trade: int = 10,
    profit_target_pct: float = 0.05,
    strategy_name: str = "utility",
    risk_aversion: float = 1.0,
    max_weight: float = 0.25,
    cash_buffer: float = 0.0,
    verbose: bool = True,
) -> Portfolio:
    """Fetch historical bars and replay them through the full trading system.

    Builds a ``TradingSystem`` with a selectable strategy (utility allocation
    by default), then iterates over daily OHLCV bars in chronological order.
    Each bar is fed into the ``FeatureEngine``; once ``daily_return`` is
    available the resulting ``MarketState`` is forwarded to the system.
    A performance summary is printed to stdout when the loop finishes.

    Args:
        symbols: Ticker symbols to include in the backtest.
        start: UTC-aware start datetime for the bar request.
        end: UTC-aware end datetime for the bar request.
        initial_cash: Starting cash balance for the paper portfolio.
        drop_threshold: Daily return threshold that triggers a buy signal
            (negative, e.g. ``-0.02`` = 2 % drop).
        shares_per_trade: Fixed share count for each buy order.
        profit_target_pct: Unrealised gain fraction at which a position is sold.
        strategy_name: ``"utility"`` or ``"buy_dip"``.
        risk_aversion: Utility coefficient used when ``strategy_name="utility"``.
        max_weight: Maximum per-symbol target weight for utility allocation.
        cash_buffer: Fraction of equity to keep as cash in utility allocation.
        verbose: When ``True`` a ``ConsoleSink`` is added to the event bus.

    Returns:
        The ``Portfolio`` instance after all bars have been processed, containing
        the final cash balance and any open positions.
    """
    fetcher = IBKRHistoricalFetcher()
    feature_engine = FeatureEngine()
    portfolio = Portfolio(cash=initial_cash)
    log_sink = LogSink()
    sinks: List[EventSink] = [log_sink]
    if verbose:
        sinks.append(ConsoleSink())
    strategy = _build_strategy(
        strategy_name=strategy_name,
        shares_per_trade=shares_per_trade,
        profit_target_pct=profit_target_pct,
        risk_aversion=risk_aversion,
        max_weight=max_weight,
        cash_buffer=cash_buffer,
    )

    system = TradingSystem(
        signal_engine=SignalEngine(
            [PercentDropRule(sym, threshold=drop_threshold) for sym in symbols]
        ),
        strategy=strategy,
        risk=BasicRiskManager(max_gross_leverage=1.0, max_position_value_frac=0.25),
        execution=PaperExecution(),
        portfolio=portfolio,
        bus=EventBus(sinks=sinks),
    )

    print(f"Fetching daily bars for {symbols} | {start.date()} → {end.date()} ...")
    bars = fetcher.get_ohlcv_bars(symbols, start, end, BarInterval.DAY_1)
    fetcher.close()
    print(f"  {len(bars)} bars fetched.\n")

    # Running price + indicator state across all symbols
    prices: Dict[str, float] = {}
    indicators: Dict[Tuple[str, str], float] = {}

    for bar in bars:
        new_feats = feature_engine.on_bar(bar)
        prices[bar.symbol] = bar.close
        indicators.update(new_feats)

        # Skip until daily_return is available for this symbol (needs 2 bars)
        if (bar.symbol, "daily_return") not in indicators:
            continue

        state = MarketState(
            prices=dict(prices),
            indicators=dict(indicators),
            timestamp=bar.ts,
        )
        state.on_bar(bar)
        system.step(state)

    _print_summary(symbols, start, end, portfolio, prices, initial_cash, log_sink)
    return portfolio


def _print_summary(
    symbols: List[str],
    start: datetime,
    end: datetime,
    portfolio: Portfolio,
    prices: Dict[str, float],
    initial_cash: float,
    log_sink: LogSink,
) -> None:
    """Print a formatted performance summary to stdout.

    Args:
        symbols: Tickers that were included in the backtest.
        start: Start of the backtest period.
        end: End of the backtest period.
        portfolio: Final portfolio state.
        prices: Most-recent close price per symbol.
        initial_cash: Starting cash used to compute P&L.
        log_sink: Event sink whose ``log`` length is reported.
    """
    final_prices = {sym: prices[sym] for sym in symbols if sym in prices}
    equity = portfolio.market_value(final_prices)
    pnl = equity - initial_cash

    print(f"\n{'=' * 52}")
    print(f"  Symbols : {', '.join(symbols)}")
    print(f"  Period  : {start.date()} → {end.date()}")
    print(f"{'=' * 52}")
    print(f"  Final equity : ${equity:>12,.2f}")
    print(f"  P&L          : ${pnl:>+12,.2f}  ({pnl / initial_cash:+.2%})")
    print(f"  Cash         : ${portfolio.cash:>12,.2f}")
    if portfolio.positions:
        print("  Open positions:")
        for sym, pos in portfolio.positions.items():
            mkt_val = pos.qty * final_prices.get(sym, pos.avg_cost)
            print(f"    {sym:>6}: {pos.qty:+5d} shares  avg ${pos.avg_cost:.2f}  mkt ${mkt_val:,.2f}")
    print(f"  Events fired : {len(log_sink.log)}")
    print(f"{'=' * 52}\n")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the backtest runner.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="Run a backtest against IBKR historical data.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], metavar="SYM")
    parser.add_argument("--start", default="2024-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default="2024-12-31", help="YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=100_000.0)
    parser.add_argument("--drop-threshold", type=float, default=-0.02)
    parser.add_argument("--shares", type=int, default=10)
    parser.add_argument("--profit-target", type=float, default=0.05)
    parser.add_argument("--strategy", choices=["utility", "buy_dip"], default="utility")
    parser.add_argument("--risk-aversion", type=float, default=1.0)
    parser.add_argument("--max-weight", type=float, default=0.25)
    parser.add_argument("--cash-buffer", type=float, default=0.0)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_backtest(
        symbols=args.symbols,
        start=datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc),
        end=datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc),
        initial_cash=args.cash,
        drop_threshold=args.drop_threshold,
        shares_per_trade=args.shares,
        profit_target_pct=args.profit_target,
        strategy_name=args.strategy,
        risk_aversion=args.risk_aversion,
        max_weight=args.max_weight,
        cash_buffer=args.cash_buffer,
        verbose=not args.quiet,
    )
