from dataclasses import dataclass

@dataclass(frozen=True)
class Action:
    """
    Represents an INTENDED trading action. NOT an order (yet).
    """
    ticker: str 
    target_position: int # “How much of this asset do I want to hold?” (e.g., + 100, 0, - 50)
    reason: str

