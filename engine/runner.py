from __future__ import annotations

from engine.state import MarketState
from engine.system import TradingSystem


class SystemRunner:
    """
    Simple orchestration wrapper around TradingSystem.
    """

    def __init__(self, system: TradingSystem):
        self.system = system

    def step(self, state: MarketState) -> None:
        self.system.step(state)
