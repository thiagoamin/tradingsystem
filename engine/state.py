from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fetchers.models import L1Quote, L2OrderBookDelta, L2OrderBookSnapshot, OHLCVBar, TradePrint


class MarketState:
    """
    Sole input to the signal engine and provides a
    stable contract between data ingestion and decision logic.

    A MarketState contains *only derived features and current values*.
    It does not own raw history. All temporal aggregation (returns,
    moving averages, volatility, regimes, etc.) is performed upstream
    in the data/feature layer.
    """

    def __init__(
        self,
        prices: Dict[str, float],
        indicators: Dict[Tuple[str, str], float],
        timestamp: datetime,
        meta: Dict[str, Any] | None = None,
    ):
        """Construct a MarketState snapshot.

        Args:
            prices: Mapping from ticker symbol to its current price.
                Example: {"AAPL": 183.4, "SPY": 471.2}.
            indicators: Mapping from (ticker, indicator_name) to a computed feature value.
                Example: ("AAPL", "ma_20") -> 182.3.
            timestamp: Time at which this snapshot is valid.
            meta: Optional auxiliary metadata (e.g., data source, regime labels).
                Not used by the signal engine directly.
        """
        self.prices = prices
        self.indicators = indicators
        self.timestamp = timestamp
        self.meta = meta or {}

        # Optional richer market data (populated by data feed)
        self.l1_quotes: Dict[str, L1Quote] = {}
        self.l2_books: Dict[str, L2OrderBookSnapshot] = {}
        self.last_bar: Dict[str, OHLCVBar] = {}
        self.last_trade: Dict[str, TradePrint] = {}

    def price(self, ticker: str) -> float:
        """Returns price for a ticker."""
        return self.prices[ticker]

    def indicator(self, ticker: str, name: str) -> float:
        """Returns indicator value for a given ticker and indicator name."""
        return self.indicators[(ticker, name)]

    def on_l1_quote(self, quote: L1Quote) -> None:
        self.l1_quotes[quote.symbol] = quote
        if quote.last is not None:
            self.prices[quote.symbol] = quote.last

    def on_l2_snapshot(self, book: L2OrderBookSnapshot) -> None:
        self.l2_books[book.symbol] = book

    def on_l2_delta(self, delta: L2OrderBookDelta) -> None:
        # Stub: for full L2 maintenance, apply deltas to a local book.
        self.meta.setdefault("l2_deltas", []).append(delta)

    def on_bar(self, bar: OHLCVBar) -> None:
        self.last_bar[bar.symbol] = bar
        self.prices[bar.symbol] = bar.close

    def on_trade(self, trade: TradePrint) -> None:
        self.last_trade[trade.symbol] = trade
        self.prices[trade.symbol] = trade.price

    def last_price(self, ticker: str) -> Optional[float]:
        return self.prices.get(ticker)

    def mid_price(self, ticker: str) -> Optional[float]:
        quote = self.l1_quotes.get(ticker)
        if quote and quote.bid is not None and quote.ask is not None:
            return (quote.bid + quote.ask) / 2.0
        return None
