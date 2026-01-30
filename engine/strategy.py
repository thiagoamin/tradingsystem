from abc import ABC, abstractmethod
from typing import List
from .state import MarketState
from .actions import Action

class Strategy(ABC):
    """
    Given a MarketState, decide what the desired position should be.
    """

    @abstractmethod
    def decide(self, state:MarketState) -> List[Action]:
        """
        Return List[Action] if a decision is made, else [].
        """
        ...