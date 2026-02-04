# fetchers/providers/csv.py
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from ..base import Capabilities, Fetcher, ProviderError
from ..models import BarInterval, L1Quote, OHLCVBar


class CSVFetcher(Fetcher):
    """
    Stub CSV-backed fetcher for backtests.

    Expected file format and parsing are left for implementation.
    """

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    @property
    def name(self) -> str:
        return "csv"

    @property
    def caps(self) -> Capabilities:
        return Capabilities(
            ohlcv_bars=True,
            l1_quotes=False,
            l2_books=False,
            trades=False,
            bid_ask_sizes=False,
            supports_adjusted_bars=False,
            max_symbols_per_request=1000,
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
        raise ProviderError("CSVFetcher.get_ohlcv_bars not implemented")

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        raise ProviderError("CSVFetcher.get_l1_quotes not implemented")
