from datetime import datetime

from engine.state import MarketState
from engine.rules import PercentDropRule, MovingAverageCrossRule


def make_state(indicators):
    return MarketState(
        prices={"AAPL": 180.0},
        indicators=indicators,
        timestamp=datetime.now()
    )


def test_percent_drop_rule_fires():
    state = make_state({("AAPL", "daily_return"): -0.05})
    rule = PercentDropRule("AAPL", threshold=-0.03)

    events = rule.evaluate(state)

    assert len(events) == 1
    ev = events[0]
    assert ev.name == "pct_drop"
    assert ev.severity == "warn"
    assert ev.payload["ticker"] == "AAPL"


def test_percent_drop_rule_no_fire():
    state = make_state({("AAPL", "daily_return"): -0.01})
    rule = PercentDropRule("AAPL", threshold=-0.03)

    events = rule.evaluate(state)

    assert events == []


def test_ma_cross_rule_fires():
    state = make_state({
        ("AAPL", "ma_20"): 181.0,
        ("AAPL", "ma_50"): 179.0,
    })
    rule = MovingAverageCrossRule("AAPL", short=20, long=50)

    events = rule.evaluate(state)

    assert len(events) == 1
    assert events[0].name == "ma_cross"


def test_ma_cross_rule_no_fire():
    state = make_state({
        ("AAPL", "ma_20"): 178.0,
        ("AAPL", "ma_50"): 180.0,
    })
    rule = MovingAverageCrossRule("AAPL", short=20, long=50)

    events = rule.evaluate(state)

    assert events == []