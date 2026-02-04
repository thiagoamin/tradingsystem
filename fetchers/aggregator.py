# fetchers/aggregator.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .base import Capabilities, Fetcher
from .models import BarInterval, OHLCVBar, L1Quote, TradePrint, L2OrderBookSnapshot


class MultiSourceFetcher(Fetcher):
    """
    Routes requests to one of several underlying providers.

    routing: optional mapping symbol -> provider_name
    default_provider: provider used when symbol isn't in routing
    """

    def __init__(
        self,
        providers: List[Fetcher],
        routing: Optional[Dict[str, str]] = None,
        default_provider: Optional[str] = None,
    ):
        self.providers: Dict[str, Fetcher] = {p.name: p for p in providers}
        self.routing: Dict[str, str] = routing or {}
        self.default_provider: Optional[str] = default_provider

    @property
    def name(self) -> str:
        return "multi"

    @property
    def caps(self) -> Capabilities:
        """Return the union of capabilities across providers (implementation omitted)."""
        raise NotImplementedError

    def _provider_for(self, symbol: str) -> Fetcher:
        """Pick a provider for a symbol using routing/default (implementation omitted)."""
        raise NotImplementedError

    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        raise NotImplementedError

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        raise NotImplementedError

    def get_trade_prints(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> List[TradePrint]:
        raise NotImplementedError

    def get_l2_order_books(
        self,
        symbols: Iterable[str],
        depth: Optional[int] = None,
    ) -> List[L2OrderBookSnapshot]:
        raise NotImplementedError