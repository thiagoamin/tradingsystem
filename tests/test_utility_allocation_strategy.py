from datetime import datetime

from allocation import MeanVarianceUtility, UtilityAllocator
from engine.events import Event
from engine.portfolio import Portfolio
from engine.state import MarketState
from engine.strategies.utility_allocation import UtilityAllocationStrategy


def test_utility_allocation_strategy_generates_target_position():
    state = MarketState(
        prices={"AAPL": 100.0},
        indicators={("AAPL", "volatility"): 0.1},
        timestamp=datetime.now(),
    )
    portfolio = Portfolio(cash=1_000.0)

    strategy = UtilityAllocationStrategy(
        allocator=UtilityAllocator(MeanVarianceUtility(risk_aversion=1.0))
    )
    signals = [
        Event(
            ts=state.timestamp,
            type="signal",
            name="forecast",
            message="alpha",
            payload={"symbol": "AAPL", "expected_return": 0.02, "volatility": 0.1},
        )
    ]

    actions = strategy.decide(state, portfolio, signals)
    assert len(actions) == 1
    assert actions[0].ticker == "AAPL"
    assert actions[0].target_qty == 10


def test_utility_allocation_strategy_uses_return_fallback_and_closes_other_positions():
    state = MarketState(
        prices={"AAPL": 100.0, "MSFT": 50.0},
        indicators={("AAPL", "vol_20"): 0.2},
        timestamp=datetime.now(),
    )
    portfolio = Portfolio(cash=1_000.0)
    portfolio.apply_fill("MSFT", 5, 50.0)

    strategy = UtilityAllocationStrategy(
        allocator=UtilityAllocator(MeanVarianceUtility(risk_aversion=1.0))
    )
    signals = [
        Event(
            ts=state.timestamp,
            type="signal",
            name="pct_drop",
            message="dip",
            payload={"ticker": "AAPL", "return": -0.03},
        )
    ]

    actions = strategy.decide(state, portfolio, signals)
    by_symbol = {a.ticker: a.target_qty for a in actions}

    assert "AAPL" in by_symbol
    assert by_symbol["AAPL"] > 0
    assert by_symbol["MSFT"] == 0
