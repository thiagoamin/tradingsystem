from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class BarInterval(str, Enum):
    """Canonical time bucket used to aggregate data"""
    MIN_1 = "1m"
    MIN_5 = "5m"
    HOUR_1 = "1h"
    DAY_1 = "1d"


class BookSide(str, Enum):
    BID = "bid"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """
    Time-bucketed OHLCV candle (typically aggregated from trades/prints).
    """
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    interval: BarInterval
    source: str
    adjusted: bool = False


@dataclass(frozen=True, slots=True)
class L1Quote:
    """
    Level 1 (top-of-book) quote snapshot: best bid/ask (+ optional sizes).
    """
    ts: datetime
    symbol: str
    bid: Optional[float]
    bid_size: Optional[float]
    ask: Optional[float]
    ask_size: Optional[float]
    last: Optional[float]     # last trade price (often included by feeds)
    source: str
    venue: Optional[str] = None  # exchange/venue or "composite"/"nbbo" depending on provider


@dataclass(frozen=True, slots=True)
class TradePrint:
    """
    Executed trade ("print"/"tape") event.
    """
    ts: datetime
    symbol: str
    price: float
    size: float
    source: str
    trade_id: Optional[str] = None
    conditions: Optional[Tuple[str, ...]] = None
    venue: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PriceLevel:
    """
    One aggregated price level in the order book.
    - size: total displayed liquidity at that level
    - order_count: number of orders aggregated at that level (if provided)
    """
    price: float
    size: float
    order_count: Optional[int] = None


@dataclass(frozen=True, slots=True)
class L2OrderBookSnapshot:
    """
    Level 2 (market depth) snapshot.

    Conventions:
      - bids: sorted high->low (best first)
      - asks: sorted low->high (best first)
    """
    ts: datetime
    symbol: str
    bids: Tuple[PriceLevel, ...]
    asks: Tuple[PriceLevel, ...]
    source: str
    depth: Optional[int] = None
    venue: Optional[str] = None 

@dataclass(frozen=True, slots=True)
class L2OrderBookDelta:
    """
    Incremental L2 update (delta): set a level's size (size=0 => remove level).
    """
    ts: datetime
    symbol: str
    side: BookSide
    price: float
    size: float
    source: str
    venue: Optional[str] = None