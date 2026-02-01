from typing import List
from .events import Event
from .sinks import EventSink

class EventBus:
    """
    Fan-out dispatcher for Events.

    EvenBus decouples event production from event consumption.
    """
    def __init__(self, sinks: List[EventSink]):
        self.sinks: List[EventSink] = sinks
    
    def publish(self, event: Event) -> None:
        for sink in self.sinks:
            sink.handle(event)
    
