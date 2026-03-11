from __future__ import annotations

from typing import Dict, List

from allocation import AssetEstimate, UtilityAllocator
from engine.actions import Action, SetTargetPosition
from engine.events import Event
from engine.portfolio import Portfolio
from engine.state import MarketState
from engine.strategy import Strategy


class UtilityAllocationStrategy(Strategy):
    """
    Production strategy that converts signal forecasts into portfolio targets.

    Expected signal payload fields:
      - symbol or ticker
      - expected_return (optional fallback: abs(return))
      - volatility (optional, falls back to state indicators/default)
    """

    def __init__(
        self,
        allocator: UtilityAllocator,
        default_volatility: float = 0.02,
    ):
        self.allocator = allocator
        self.default_volatility = default_volatility

    def decide(
        self,
        state: MarketState,
        portfolio: Portfolio,
        signals: List[Event],
    ) -> List[Action]:
        estimates = self._build_estimates(state, signals)
        if not estimates:
            return []

        equity = portfolio.market_value(state.prices)
        target_qtys = self.allocator.target_quantities(estimates, state.prices, equity)

        actions: List[Action] = []
        symbols = set(portfolio.positions.keys()) | set(target_qtys.keys())
        for symbol in symbols:
            target_qty = target_qtys.get(symbol, 0)
            if target_qty == portfolio.get_qty(symbol):
                continue
            actions.append(
                SetTargetPosition(
                    reason=f"utility_allocation:{self.allocator.utility.name}",
                    ticker=symbol,
                    target_qty=target_qty,
                )
            )
        return actions

    def _build_estimates(
        self,
        state: MarketState,
        signals: List[Event],
    ) -> List[AssetEstimate]:
        by_symbol: Dict[str, AssetEstimate] = {}
        for sig in signals:
            payload = sig.payload if isinstance(sig.payload, dict) else None
            if not payload:
                continue

            symbol = payload.get("symbol") or payload.get("ticker")
            if not symbol or symbol not in state.prices:
                continue

            expected_return = payload.get("expected_return")
            if expected_return is None and payload.get("return") is not None:
                expected_return = abs(float(payload["return"]))
            if expected_return is None:
                continue

            volatility = payload.get("volatility")
            if volatility is None:
                volatility = (
                    state.indicators.get((symbol, "volatility"))
                    or state.indicators.get((symbol, "daily_volatility"))
                    or state.indicators.get((symbol, "vol_20"))
                    or self.default_volatility
                )

            by_symbol[symbol] = AssetEstimate(
                symbol=symbol,
                expected_return=float(expected_return),
                volatility=float(volatility),
            )

        return list(by_symbol.values())
