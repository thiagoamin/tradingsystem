from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ...base import Capabilities, Fetcher, ProviderError
from ...models import BarInterval, L1Quote, L2OrderBookSnapshot, OHLCVBar, TradePrint
from .common import _IBGatewayError
from .gateway import _NativeIBGateway

class IBKRLiveFetcher(Fetcher):
    """Live quote fetcher and order router for IBKR paper/live accounts."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        """Initialise the live fetcher.

        Args:
            host: Hostname of the TWS / IB Gateway process.
            port: Port number.
            client_id: Unique client-ID for this session.
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self._gateway = _NativeIBGateway(host=host, port=port, client_id=client_id)

    @property
    def name(self) -> str:
        """Return the provider name identifier."""
        return "ibkr-live"

    @property
    def caps(self) -> Capabilities:
        """Return the capability flags for this provider."""
        return Capabilities(ohlcv_bars=False, l1_quotes=True, l2_books=False, trades=False)

    def close(self) -> None:
        """Disconnect from TWS / IB Gateway."""
        self._gateway.close()

    def _ensure_connected(self) -> None:
        """Ensure the underlying gateway is connected, connecting if needed."""
        self._gateway.connect()

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        """Fetch current L1 (top-of-book) quotes for one or more symbols.

        Args:
            symbols: Iterable of ticker symbols (case-insensitive).

        Returns:
            List of ``L1Quote`` objects, one per symbol, in input order.

        Raises:
            ProviderError: If a symbol is empty or the gateway returns an error.
        """
        self._ensure_connected()
        quotes: List[L1Quote] = []
        for symbol in self._normalize_symbols(symbols):
            raw = self._gateway.request_l1_snapshot(
                self._build_contract(symbol),
                timeout_sec=15.0,
            )
            quotes.append(L1Quote(
                ts=self._as_utc(raw.ts),
                symbol=symbol,
                bid=raw.bid,
                bid_size=raw.bid_size,
                ask=raw.ask,
                ask_size=raw.ask_size,
                last=raw.last,
                source=self.name,
                venue=raw.venue,
            ))
        return quotes

    def place_order(self, symbol: str, qty: int, timeout_sec: float = 30.0) -> Tuple[float, float]:
        """Place a market order. qty > 0 = buy, qty < 0 = sell.

        Args:
            symbol: Ticker symbol (case-insensitive).
            qty: Signed quantity: positive to buy, negative to sell.
            timeout_sec: Seconds to wait for an acknowledged or filled status.

        Returns:
            Tuple of ``(avg_fill_price, filled_qty)``.

        Raises:
            ProviderError: If the order is rejected or the gateway returns an error.
        """
        self._ensure_connected()
        action = "BUY" if qty > 0 else "SELL"
        try:
            return self._gateway.place_market_order(
                self._build_contract(symbol), qty, action, timeout_sec
            )
        except _IBGatewayError as exc:
            raise ProviderError(f"IBKR order failed for {symbol}: {exc.message}") from exc

    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        """Not supported by this provider.

        Raises:
            ProviderError: Always.
        """
        raise ProviderError("IBKRLiveFetcher does not provide historical bars")

    def get_trade_prints(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> List[TradePrint]:
        """Not supported by this provider.

        Raises:
            ProviderError: Always.
        """
        raise ProviderError("IBKRLiveFetcher does not provide historical trades")

    def get_l2_order_books(
        self,
        symbols: Iterable[str],
        depth: Optional[int] = None,
    ) -> List[L2OrderBookSnapshot]:
        """Not supported by this provider.

        Raises:
            ProviderError: Always.
        """
        raise ProviderError("IBKRLiveFetcher does not provide L2 books")

    def _normalize_symbols(self, symbols: Iterable[str]) -> List[str]:
        """Strip, upper-case, and deduplicate symbols while preserving order.

        Args:
            symbols: Raw symbol iterable from the caller.

        Returns:
            Deduplicated list of upper-cased symbols.

        Raises:
            ProviderError: If the resulting list is empty.
        """
        normalized = [sym.strip().upper() for sym in symbols if sym and sym.strip()]
        if not normalized:
            raise ProviderError("at least one symbol is required")
        return list(dict.fromkeys(normalized))

    def _build_contract(self, symbol: str) -> Dict[str, Any]:
        """Build a default US equity IB contract dict for ``symbol``.

        Args:
            symbol: Normalised (upper-cased) ticker symbol.

        Returns:
            Contract specification dict.
        """
        return {"symbol": symbol.upper(), "secType": "STK", "exchange": "SMART", "currency": "USD"}

    @staticmethod
    def _as_utc(ts: datetime) -> datetime:
        """Coerce ``ts`` to UTC, attaching ``timezone.utc`` if naive.

        Args:
            ts: Input datetime (may be naive or timezone-aware).

        Returns:
            Timezone-aware datetime in UTC.
        """
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

