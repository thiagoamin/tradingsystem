from abc import ABC, abstractmethod
from typing import List
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
    @abstractmethod
    def handle(self, event: SignalEvent) -> None:
        """
        Handles a SignalEvent. 
        """
        ...

class EventBus:
    """
    Fan-out dispatcher for SignalEvents.

    EvenBus decouples event production from event consumption.
    """
    def __init__(self, sinks: List[EventSink]):
        self.sinks: List[EventSink] = sinks
    
    def publish(self, event: SignalEvent) -> None:
        for sink in self.sinks:
            sink.handle(event)
    
