# fetchers/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from .models import (
    BarInterval,
    OHLCVBar,
    L1Quote,
    TradePrint,
    L2OrderBookSnapshot,
)


class FetcherError(Exception):
    """Base class for fetcher/provider-related errors."""


class RateLimitError(FetcherError):
    """Raised when provider rate limits are hit."""


class ProviderError(FetcherError):
    """Raised for provider-side failures (HTTP 5xx, bad responses, etc.)."""


@dataclass(frozen=True, slots=True)
class Capabilities:
    """
    Describes what a given provider supports.

    Notes:
      - l1_quotes: provider can return L1Quote objects
      - l2_books: provider can return L2 order book snapshots
      - trades: provider can return trade prints
      - bid_ask_sizes: L1 quotes include bid_size/ask_size (some feeds omit sizes)
    """
    ohlcv_bars: bool = True
    l1_quotes: bool = True
    l2_books: bool = False
    trades: bool = False

    bid_ask_sizes: bool = False
    supports_adjusted_bars: bool = False

    max_symbols_per_request: int = 50
    max_l2_depth: Optional[int] = None


class Fetcher(ABC):
    """
    Provider adapter interface.

    Implementations normalize provider responses into the canonical models in
    fetchers/models.py.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider identifier, e.g. 'alpaca', 'polygon', 'ibkr'."""
        ...

    @property
    @abstractmethod
    def caps(self) -> Capabilities:
        """Capabilities supported by this provider."""
        ...

    @abstractmethod
    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        """
        Fetch OHLCV bars for each symbol in [start, end).

        Conventions:
          - Implementations should normalize timestamps consistently (recommend UTC).
          - 'adjusted' should be honored only if caps.supports_adjusted_bars is True;
            otherwise raise ProviderError (or ignore and document, but raising is safer).
        """
        ...

    @abstractmethod
    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        """
        Fetch L1 (top-of-book) quotes for the given symbols.

        If caps.bid_ask_sizes is False, implementations may return bid_size/ask_size as None.
        """
        ...

    # Optional endpoints (only implement if supported; otherwise raise ProviderError)

    def get_trade_prints(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> List[TradePrint]:
        """
        Fetch executed trades ("prints") for each symbol in [start, end).
        """
        raise ProviderError(f"{self.name} does not support trade prints")

    def get_l2_order_books(
        self,
        symbols: Iterable[str],
        depth: Optional[int] = None,
    ) -> List[L2OrderBookSnapshot]:
        """
        Fetch L2 order book snapshots for the given symbols.

        depth: number of levels per side (best-to-worst). If None, provider default.
        If caps.max_l2_depth is not None, depth should not exceed it.
        """
        raise ProviderError(f"{self.name} does not support L2 order books")