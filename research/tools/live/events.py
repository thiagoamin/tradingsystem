from dataclasses import dataclass
from typing import Any, Literal, Optional
from datetime import datetime

Severity = Literal["debug", "info", "warn", "critical"]
EventType = Literal["signal", "decision", "risk", "order", "fill", "system"]

@dataclass(frozen=True)
class Event:
    ts: datetime
    type: EventType
    name: str
    message: str
    severity: Severity = "info"
    payload: Optional[Any] = None