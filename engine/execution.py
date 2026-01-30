from abc import ABC, abstractmethod
from typing import List
from .actions import Action
from .events import SignalEvent
from .state import MarketState

class ExecutionEngine(ABC):
    """
    Translates Actions into actual trades.
    """
    @abstractmethod
    def apply(self, action: Action, state: MarketState) -> List[SignalEvent]:
        """
        Execute the action and emit trade-related events (or [] if none).
        """
        ...