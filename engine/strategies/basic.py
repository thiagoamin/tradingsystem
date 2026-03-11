from __future__ import annotations

from typing import List

from engine.actions import Action
from engine.events import Event
from engine.portfolio import Portfolio
from engine.state import MarketState
from engine.strategy import Strategy


class BuyDipStrategy(Strategy):
    """
    Placeholder strategy. Extend with real signal->action logic.
    """

    def __init__(self, shares_per_trade: int = 10, profit_target_pct: float = 0.05):
        # Stored now so runner configs are valid even before decide() is implemented.
        self.shares_per_trade = shares_per_trade
        self.profit_target_pct = profit_target_pct

    def decide(self, state: MarketState, portfolio: Portfolio, signals: List[Event]) -> List[Action]:
        # TODO: use signals to choose target positions
        return []
