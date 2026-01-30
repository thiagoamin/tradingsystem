from datetime import datetime

from engine.engine import MarketState
from engine.engine import SignalEngine
from engine.rules import PercentDropRule, MovingAverageCrossRule


def test_engine_aggregates_events():
    state = MarketState(
        prices={"AAPL": 180.0},
        indicators={
            ("AAPL", "daily_return"): -0.05,
            ("AAPL", "ma_20"): 181.0,
            ("AAPL", "ma_50"): 179.0,
        },
        timestamp=datetime.now(),
    )

    rules = [
        PercentDropRule("AAPL", threshold=-0.03),
        MovingAverageCrossRule("AAPL", short=20, long=50),
    ]

    engine = SignalEngine(rules)
    events = engine.run(state)

    names = {e.name for e in events}
    assert names == {"pct_drop", "ma_cross"}