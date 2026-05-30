# engine/risk.py
from abc import ABC, abstractmethod
from typing import List, Tuple
from .portfolio import Portfolio
from .state import MarketState
from .events import Event
from .actions import Action

class RiskManager(ABC):
    @abstractmethod
    def filter(self, actions: List[Action], portfolio: Portfolio, state: MarketState) -> Tuple[List[Action], List[Event]]:
        """
        Returns:
          - allowed actions (possibly modified)
          - risk events (explanations / blocks)
        """
        ...

class BasicRiskManager(RiskManager):
    def __init__(self, max_gross_leverage: float = 1.0, max_position_value_frac: float = 0.25):
        self.max_gross = max_gross_leverage
        self.max_pos_frac = max_position_value_frac

    def filter(self, actions, portfolio, state):
        events: List[Event] = []
        allowed = list(actions)

        # Stub: later compute leverage/limits properly.
        # For now, do nothing but keep the interface stable.
        return allowed, events

    def _gross_exposure(self, portfolio: Portfolio, state: MarketState) -> float:
        # TODO: compute sum(|qty| * price)
        return 0.0

    def _equity(self, portfolio: Portfolio, state: MarketState) -> float:
        # TODO: compute cash + market value
        return 0.0
