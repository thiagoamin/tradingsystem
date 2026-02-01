from abc import ABC
from dataclasses import dataclass

@dataclass(frozen=True)
class Action(ABC):
    """
    Base class for all strategy intents.

    An Action represents *what the strategy wants*, not *how to execute it*.
    """
    reason: str

@dataclass(frozen=True)
class SetTargetPosition(Action):
    """
    ...
    """
    ticker: str
    target_qty: int

