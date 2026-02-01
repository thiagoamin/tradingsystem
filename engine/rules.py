from abc import ABC, abstractmethod
from typing import List, Optional

from .state import MarketState
from .events import Event

class Rule(ABC):
    """
    Anything that can evaluate a MarketState and emit zero or more Events.
        'Given this MarketState, should I emit signals?'
    """
    @abstractmethod
    def evaluate(self, state: MarketState) -> List[Event]:
        ...

class AtomicRule(ABC):
    """ Anything that can evaluate a MarketState and emit zero or one Events.
        Subclasses implement `_evaluate_one`.
    """

    def evaluate(self, state: MarketState) -> List[Event]:
        event = self._evaluate_one(state)
        return [event] if event is not None else []

    @abstractmethod
    def _evaluate_one(self, state: MarketState) -> Optional[Event]:
        """Return an Event if the rule fires, otherwise None."""
        ...

class PercentDropRule(AtomicRule):
    def __init__(self, ticker: str, threshold: float):
        self.ticker = ticker
        self.threshold = threshold

    def _evaluate_one(self, state: MarketState):
        ret = state.indicator(self.ticker, "daily_return")
        if ret <= self.threshold:
            return Event(
                ts=state.timestamp,
                type="signal",
                name="pct_drop",
                message=f"{self.ticker} dropped {ret:.2%}",
                severity="warn",
                payload={"ticker": self.ticker, "return": ret},
            )
        return None

class MovingAverageCrossRule(AtomicRule):
    def __init__(self, ticker: str, short: int, long: int):
        self.ticker = ticker
        self.short = short
        self.long = long

    def _evaluate_one(self, state: MarketState):
        s = state.indicator(self.ticker, f"ma_{self.short}")
        l = state.indicator(self.ticker, f"ma_{self.long}")
        if s > l:
            return Event(
                ts=state.timestamp,
                type="signal",
                name="ma_cross",
                message=f"{self.ticker}: MA{self.short} crossed above MA{self.long}",
                severity="info",
            )
        return None
