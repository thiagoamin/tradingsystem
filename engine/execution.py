# engine/execution.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from .actions import Action, SetTargetPosition
from .portfolio import Portfolio
from .state import MarketState
from .events import Event

@dataclass(frozen=True)
class Fill:
    symbol: str
    qty: int
    price: float
    ts: datetime

class ExecutionEngine(ABC):
    @abstractmethod
    def execute(self, actions: List[Action], portfolio: Portfolio, state: MarketState) -> tuple[List[Fill], List[Event]]:
        ...

class PaperExecution(ExecutionEngine):
    def execute(self, actions, portfolio, state):
        fills: List[Fill] = []
        events: List[Event] = []

        # Stub: implement action handling gradually.
        # Example: SetTargetPosition -> immediate fill at last price.
        for a in actions:
            if isinstance(a, SetTargetPosition):
                current_qty = portfolio.get_qty(a.ticker)
                delta_qty = a.target_qty - current_qty
                if delta_qty == 0:
                    continue

                px = state.price(a.ticker)
                fill = Fill(a.ticker, delta_qty, px, state.timestamp)
                portfolio.apply_fill(a.ticker, delta_qty, px)
                fills.append(fill)

        return fills, events
