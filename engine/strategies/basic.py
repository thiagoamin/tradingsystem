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

    def decide(self, state: MarketState, portfolio: Portfolio, signals: List[Event]) -> List[Action]:
        # TODO: use signals to choose target positions
        return []
