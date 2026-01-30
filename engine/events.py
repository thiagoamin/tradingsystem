from dataclasses import dataclass
from typing import Any

@dataclass
class SignalEvent:
    name: str
    message: str
    severity: str  # "info", "warn", "critical"
    payload: Any = None