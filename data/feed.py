from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
from fetchers.base import Fetcher
from fetchers.models import BarInterval, L1Quote, OHLCVBar

from .feature_engine import FeatureEngine


class DataFeed:
    """
    Base data feed abstraction. Concrete feeds can be historical or live.
    """

    def __init__(self, fetcher: Fetcher, feature_engine: FeatureEngine):
        self.fetcher = fetcher
        self.feature_engine = feature_engine


class HistoricalFeed(DataFeed):
    """
    Historical data feed for backtests.
    """

    def historical_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        return self.fetcher.get_ohlcv_bars(symbols, start, end, interval, adjusted=adjusted)


class LiveFeed(DataFeed):
    """
    Live data feed for realtime trading.
    """

    def latest_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        return self.fetcher.get_l1_quotes(symbols)
