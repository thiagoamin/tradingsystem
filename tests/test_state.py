from datetime import datetime

from engine.state import MarketState


def test_market_state_accessors():
    now = datetime.now()

    state = MarketState(
        prices={"AAPL": 180.0},
        indicators={("AAPL", "ma_20"): 175.0},
        timestamp=now,
    )

    assert state.price("AAPL") == 180.0
    assert state.indicator("AAPL", "ma_20") == 175.0
    assert state.timestamp == now
    assert isinstance(state.meta, dict)