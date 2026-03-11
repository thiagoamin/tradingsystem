#!/usr/bin/env python
"""
Paper trading runner — connects to the IBKR paper account (port 7497),
bootstraps indicators from recent historical bars, then polls live quotes
and runs the trading system on a fixed interval.

Usage:
    python paper_trade.py
    python paper_trade.py --symbols AAPL MSFT --interval 30
"""

from __future__ import annotations

import argparse
import signal
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from allocation import MeanVarianceUtility, UtilityAllocator
from data.feature_engine import FeatureEngine
from engine.bus import EventBus
from engine.engine import SignalEngine
from engine.execution_ibkr import IBKRExecution
from engine.portfolio import Portfolio
from engine.risk import BasicRiskManager
from engine.rules import PercentDropRule
from engine.sinks import ConsoleSink, LogSink
from engine.state import MarketState
from engine.strategy import Strategy
from engine.strategies.basic import BuyDipStrategy
from engine.strategies.utility_allocation import UtilityAllocationStrategy
from engine.system import TradingSystem
from fetchers.models import BarInterval
from fetchers.providers.ibkr import IBKRHistoricalFetcher, IBKRLiveFetcher

# IBKR paper account uses port 7497 (TWS) or 4002 (IB Gateway).
# Live account uses port 7496 (TWS) or 4001 (IB Gateway).
PAPER_PORT = 7497


def _compute_return(new_price: float, prev_price: float) -> float:
    if prev_price <= 0:
        return 0.0
    return (new_price - prev_price) / prev_price


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


def run_paper_trade(
    symbols: List[str],
    initial_cash: float = 100_000.0,
    poll_interval_sec: float = 30.0,
    drop_threshold: float = -0.02,
    shares_per_trade: int = 10,
    profit_target_pct: float = 0.05,
    strategy_name: str = "utility",
    risk_aversion: float = 1.0,
    max_weight: float = 0.25,
    cash_buffer: float = 0.0,
    host: str = "127.0.0.1",
    port: int = PAPER_PORT,
    bootstrap_days: int = 60,
) -> None:
    """Run the trading system against an IBKR paper account indefinitely.

    On startup the ``FeatureEngine`` is seeded with the last ``bootstrap_days``
    of daily bars so that indicators such as moving averages are warm before live
    trading begins.  The main loop then polls L1 quotes, builds a ``MarketState``,
    and calls ``system.step`` every ``poll_interval_sec`` seconds.  A SIGINT
    (Ctrl+C) triggers a graceful shutdown: the loop exits, the live connection is
    closed, and a final P&L summary is printed.

    Args:
        symbols: Ticker symbols to trade.
        initial_cash: Starting cash balance for the paper portfolio.
        poll_interval_sec: Seconds between each live-quote poll and system step.
        drop_threshold: Daily return threshold that triggers a buy signal.
        shares_per_trade: Fixed share count for each buy order.
        profit_target_pct: Unrealised gain fraction at which a position is sold.
        strategy_name: ``"utility"`` or ``"buy_dip"``.
        risk_aversion: Utility coefficient used when ``strategy_name="utility"``.
        max_weight: Maximum per-symbol target weight for utility allocation.
        cash_buffer: Fraction of equity to keep as cash in utility allocation.
        host: Hostname or IP address of the TWS / IB Gateway instance.
        port: Port of the TWS / IB Gateway instance.
        bootstrap_days: Number of calendar days of historical bars to fetch for
            indicator warm-up.
    """
    # Two separate client IDs: one for historical bootstrap, one for live trading.
    live_fetcher = IBKRLiveFetcher(host=host, port=port, client_id=2)
    portfolio = Portfolio(cash=initial_cash)
    feature_engine = FeatureEngine()
    log_sink = LogSink()
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
        execution=IBKRExecution(live_fetcher),
        portfolio=portfolio,
        bus=EventBus(sinks=[log_sink, ConsoleSink()]),
    )

    prices, indicators = _bootstrap_indicators(
        symbols, host, port, bootstrap_days, feature_engine
    )
    missing_indicator_warned = False

    # Graceful shutdown on Ctrl+C
    running = True

    def _shutdown(signum, frame) -> None:  # noqa: ARG001
        """Handle SIGINT by setting the loop-termination flag."""
        nonlocal running
        print("\nShutting down...")
        running = False

    signal.signal(signal.SIGINT, _shutdown)

    print(f"Paper trading {symbols} | poll every {poll_interval_sec}s | Ctrl+C to stop\n")

    try:
        while running:
            try:
                quotes = live_fetcher.get_l1_quotes(symbols)
            except Exception as exc:
                print(f"[ERROR] Quote fetch failed: {exc}")
                time.sleep(poll_interval_sec)
                continue

            for quote in quotes:
                if quote.last is not None:
                    prev_price = prices.get(quote.symbol)
                    prices[quote.symbol] = quote.last
                    if prev_price is not None:
                        indicators[(quote.symbol, "daily_return")] = _compute_return(
                            quote.last,
                            prev_price,
                        )

            ready = all((symbol, "daily_return") in indicators for symbol in symbols)
            if not ready:
                if not missing_indicator_warned:
                    print("Waiting for daily_return indicators before stepping the system...")
                    missing_indicator_warned = True
                time.sleep(poll_interval_sec)
                continue
            missing_indicator_warned = False

            ts = datetime.now(tz=timezone.utc)
            state = MarketState(prices=dict(prices), indicators=dict(indicators), timestamp=ts)
            for quote in quotes:
                state.on_l1_quote(quote)

            system.step(state)

            equity = portfolio.market_value(prices)
            pnl = equity - initial_cash
            pos_summary = ", ".join(
                f"{sym} {pos.qty:+d}" for sym, pos in portfolio.positions.items()
            ) or "flat"
            print(
                f"[{ts:%H:%M:%S}]  equity=${equity:,.0f}  pnl={pnl:+,.0f} ({pnl/initial_cash:+.2%})"
                f"  positions=[{pos_summary}]"
            )

            time.sleep(poll_interval_sec)
    finally:
        live_fetcher.close()
    final_equity = portfolio.market_value(prices)
    final_pnl = final_equity - initial_cash
    print(f"\nSession ended.  Final equity: ${final_equity:,.2f}  P&L: ${final_pnl:+,.2f}")


def _bootstrap_indicators(
    symbols: List[str],
    host: str,
    port: int,
    bootstrap_days: int,
    feature_engine: FeatureEngine,
) -> Tuple[Dict[str, float], Dict[Tuple[str, str], float]]:
    """Fetch historical bars and warm up the feature engine before live trading.

    Args:
        symbols: Ticker symbols to fetch historical bars for.
        host: TWS / IB Gateway hostname.
        port: TWS / IB Gateway port.
        bootstrap_days: Number of calendar days of history to request.
        feature_engine: Feature engine instance to seed with historical bars.

    Returns:
        A tuple ``(prices, indicators)`` where ``prices`` maps each symbol to its
        most-recent close price and ``indicators`` contains all computed feature
        values keyed by ``(symbol, feature_name)``.
    """
    print(f"Bootstrapping indicators from last {bootstrap_days} days of daily bars...")
    hist_fetcher = IBKRHistoricalFetcher(host=host, port=port, client_id=1)
    now = datetime.now(tz=timezone.utc)
    bars = hist_fetcher.get_ohlcv_bars(
        symbols,
        start=now - timedelta(days=bootstrap_days),
        end=now,
        interval=BarInterval.DAY_1,
    )
    hist_fetcher.close()

    prices: Dict[str, float] = {}
    indicators: Dict[Tuple[str, str], float] = {}
    for bar in bars:
        new_feats = feature_engine.on_bar(bar)
        prev_price = prices.get(bar.symbol)
        prices[bar.symbol] = bar.close
        indicators.update(new_feats)
        if prev_price is not None:
            indicators[(bar.symbol, "daily_return")] = _compute_return(bar.close, prev_price)
    print(f"  {len(bars)} bars bootstrapped. Indicators ready: {len(indicators)}\n")
    return prices, indicators


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the paper trading runner.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="Paper trade via IBKR (port 7497).")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], metavar="SYM")
    parser.add_argument("--cash", type=float, default=100_000.0)
    parser.add_argument("--interval", type=float, default=30.0, help="Poll interval in seconds")
    parser.add_argument("--drop-threshold", type=float, default=-0.02)
    parser.add_argument("--shares", type=int, default=10)
    parser.add_argument("--profit-target", type=float, default=0.05)
    parser.add_argument("--strategy", choices=["utility", "buy_dip"], default="utility")
    parser.add_argument("--risk-aversion", type=float, default=1.0)
    parser.add_argument("--max-weight", type=float, default=0.25)
    parser.add_argument("--cash-buffer", type=float, default=0.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PAPER_PORT)
    parser.add_argument("--bootstrap-days", type=int, default=60)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_paper_trade(
        symbols=args.symbols,
        initial_cash=args.cash,
        poll_interval_sec=args.interval,
        drop_threshold=args.drop_threshold,
        shares_per_trade=args.shares,
        profit_target_pct=args.profit_target,
        strategy_name=args.strategy,
        risk_aversion=args.risk_aversion,
        max_weight=args.max_weight,
        cash_buffer=args.cash_buffer,
        host=args.host,
        port=args.port,
        bootstrap_days=args.bootstrap_days,
    )
