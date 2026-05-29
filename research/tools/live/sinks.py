from abc import abstractmethod, ABC
from typing import List
from .events import Event

class EventSink(ABC):
    """
    EventSink represents any downstream destination that consumes an Event emitted by trading system. 
    
    Some sinks include:
        - console/log output
        - JSON/disk persistance
        - push notifications

    EventSink must NOT modify event, only trigger events' "side-effects".
    """
    @abstractmethod
    def handle(self, event: Event) -> None:
        """
        Handles an Event. 
        """
        ...

class LogSink(EventSink):
    """
    In-memory full event log.
    """
    def __init__(self):
        self.log: List[Event] = []
    
    def handle(self, event: Event):
        self.log.append(event)

class ConsoleSink(EventSink):
    """
    Console dump of full event log (in real time). 
    """
    def handle(self, event):
        print(event)
