from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Position:
    """
    Represents an open position. qty > 0 => long, qty < 0 => short
    """
    symbol: str
    qty: int
    avg_cost: float
    avg_pnl: float 

class Portfolio:
    """
    Docstring for Porfolio
    """
    def __init__(self, cash: float):
        self.cash: float = cash
        self.positions: Dict[str, Position] = {}
    
    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)
    
    def get_qty(self, symbol: str) -> int:
        position = self.positions.get(symbol)
        return 0 if (position is None) else position.qty

    def apply_fill(self, symbol: str, qty: int, price: float) -> None:
        """
        Apply a fill to the portfolio, updating cash and position state.
        """
        if qty == 0:
            return

        self.cash -= qty * price
        position = self.positions.get(symbol)

        if position is None:
            self.positions[symbol] = Position(
                symbol=symbol,
                qty=qty,
                avg_cost=price,
                avg_pnl=0.0,
            )
            return

        new_qty = position.qty + qty
        if new_qty == 0:
            del self.positions[symbol]
            return

        # If position flips direction, reset avg_cost to the fill price.
        if (position.qty > 0 and new_qty < 0) or (position.qty < 0 and new_qty > 0):
            position.qty = new_qty
            position.avg_cost = price
            position.avg_pnl = 0.0
            return

        # Same direction: weighted average cost.
        total_cost = position.avg_cost * position.qty + price * qty
        position.qty = new_qty
        position.avg_cost = total_cost / new_qty
        position.avg_pnl = 0.0
    
    def market_value(self, prices: Dict[str, float]) -> float:
        """
        Portfolio equity estimate.
        """
        value = self.cash
        for symbol, position in self.positions.items():
            value += position.qty * prices.get(symbol, 0.0)
        return value
    
    # more methods here later
