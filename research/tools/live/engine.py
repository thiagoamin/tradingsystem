from typing import Iterable, List

from .state import MarketState
from .events import Event
from .rules import Rule


class SignalEngine:
    def __init__(self, rules: Iterable[Rule]):
        self.rules = list(rules)

    def run(self, state: MarketState) -> List[Event]:
        events: List[Event] = []
        for rule in self.rules:
            events.extend(rule.evaluate(state))
        return events
