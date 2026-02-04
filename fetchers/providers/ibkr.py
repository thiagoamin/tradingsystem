# fetchers/providers/ibkr.py
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from ..base import Capabilities, Fetcher, ProviderError
from ..models import BarInterval, L1Quote, L2OrderBookSnapshot, OHLCVBar, TradePrint


class IBKRFetcher(Fetcher):
    """
    Stub adapter for Interactive Brokers.

    Implement with ib_insync or the native IBKR API later.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id

    @property
    def name(self) -> str:
        return "ibkr"

    @property
    def caps(self) -> Capabilities:
        return Capabilities(
            ohlcv_bars=True,
            l1_quotes=True,
            l2_books=True,
            trades=True,
            bid_ask_sizes=True,
            supports_adjusted_bars=False,
            max_symbols_per_request=50,
            max_l2_depth=None,
        )

    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        raise ProviderError("IBKRFetcher.get_ohlcv_bars not implemented")

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        raise ProviderError("IBKRFetcher.get_l1_quotes not implemented")

    def get_trade_prints(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> List[TradePrint]:
        raise ProviderError("IBKRFetcher.get_trade_prints not implemented")

    def get_l2_order_books(
        self,
        symbols: Iterable[str],
        depth: int | None = None,
    ) -> List[L2OrderBookSnapshot]:
        raise ProviderError("IBKRFetcher.get_l2_order_books not implemented")
