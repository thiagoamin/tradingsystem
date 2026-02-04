# fetchers/cache.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .base import Fetcher
from .models import BarInterval, L1Quote, OHLCVBar


@dataclass
class CacheKey:
    symbols: Tuple[str, ...]
    start: datetime
    end: datetime
    interval: BarInterval
    adjusted: bool


class CachedFetcher(Fetcher):
    """
    Stub caching wrapper for any Fetcher.

    Implement using disk or in-memory storage later.
    """

    def __init__(self, upstream: Fetcher):
        self.upstream = upstream
        self._bar_cache: Dict[CacheKey, List[OHLCVBar]] = {}

    @property
    def name(self) -> str:
        return f"cached:{self.upstream.name}"

    @property
    def caps(self):
        return self.upstream.caps

    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        key = CacheKey(tuple(symbols), start, end, interval, adjusted)
        if key not in self._bar_cache:
            self._bar_cache[key] = self.upstream.get_ohlcv_bars(
                symbols, start, end, interval, adjusted=adjusted
            )
        return list(self._bar_cache[key])

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        return self.upstream.get_l1_quotes(symbols)
