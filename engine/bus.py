from abc import ABC, abstractmethod
from typing import Iterable
from .events import SignalEvent

class EventSink(ABC):
    """
    EventSink represents any downstream destination that consumes a SignalEvent emitted by trading system. 
    
    Some sinks include:
        - console/log output
        - JSON/disk persistance
        - push notifications

    EventSink must NOT modify event, only trigger events' "side-effects".
    """

class EventBus:
    """
    Docstring for EventBus
    """
