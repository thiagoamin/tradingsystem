# engine/system.py
from typing import List

from .state import MarketState
from .portfolio import Portfolio
from .engine import SignalEngine
from .strategy import Strategy
from .risk import RiskManager
from .execution import ExecutionEngine
from .bus import EventBus
from .events import Event
from datetime import datetime

class TradingSystem:
    def __init__(
        self,
        signal_engine: SignalEngine,
        strategy: Strategy,
        risk: RiskManager,
        execution: ExecutionEngine,
        portfolio: Portfolio,
        bus: EventBus,
    ):
        self.signal_engine = signal_engine
        self.strategy = strategy
        self.risk = risk
        self.execution = execution
        self.portfolio = portfolio
        self.bus = bus

    def step(self, state: MarketState) -> None:
        # 1) signals
        signals = self.signal_engine.run(state)
        for e in signals:
            self.bus.publish(e)

        # 2) decide
        actions = self.strategy.decide(state, self.portfolio, signals)
        self.bus.publish(Event(
            ts=state.timestamp,
            type="decision",
            name="ACTIONS_PROPOSED",
            message=f"{len(actions)} actions proposed",
            payload={"actions": [a.__dict__ for a in actions]},
        ))

        # 3) risk filter
        allowed, risk_events = self.risk.filter(actions, self.portfolio, state)
        for e in risk_events:
            self.bus.publish(e)

        # 4) execute
        fills, exec_events = self.execution.execute(allowed, self.portfolio, state)
        for e in exec_events:
            self.bus.publish(e)

        if fills:
            self.bus.publish(Event(
                ts=state.timestamp,
                type="fill",
                name="FILLS",
                message=f"{len(fills)} fills applied",
                payload={"fills": [f.__dict__ for f in fills]},
            ))
