from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ...base import Capabilities, Fetcher, ProviderError, RateLimitError
from ...models import (
    BarInterval,
    L1Quote,
    L2OrderBookSnapshot,
    OHLCVBar,
    PriceLevel,
    TradePrint,
)
from .common import (
    _IBGateway,
    _IBGatewayError,
    _INTERVAL_TO_BAR_SIZE,
    _INTERVAL_TO_CHUNK_DURATION,
    _INTERVAL_STEP,
    _PACED_ERROR_CODES,
    _RawBar,
    _RawBook,
    _RawQuote,
    _RawTrade,
)
from .gateway import _NativeIBGateway

class IBKRHistoricalFetcher(Fetcher):
    """Historical/market-data fetcher backed by Interactive Brokers.

    Wraps ``_NativeIBGateway`` (or a compatible ``_IBGateway`` injected for
    testing) with per-symbol pagination, local pacing enforcement, and
    conversion to the project's public model types.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        *,
        symbol_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        timeout_sec: float = 15.0,
        use_rth: bool = True,
        default_what_to_show: str = "TRADES",
        l2_warmup_sec: float = 1.5,
        gateway: Optional[_IBGateway] = None,
    ):
        """Initialise the fetcher.

        Args:
            host: Hostname of the TWS / IB Gateway process.
            port: Port number (7497 for TWS paper, 4002 for IB Gateway live).
            client_id: Client-ID used to identify this connection.
            symbol_overrides: Optional mapping of ticker symbol to a partial IB
                contract dict that overrides the defaults (e.g. to set
                ``"exchange"`` or ``"secType"`` for non-US equities).
            timeout_sec: Default seconds to wait for each gateway response.
            use_rth: If ``True``, restrict all data requests to regular trading
                hours.
            default_what_to_show: Data type passed to IBKR for bar requests
                when ``adjusted=False`` (e.g. ``"TRADES"`` or ``"MIDPOINT"``).
            l2_warmup_sec: Extra seconds to accumulate L2 updates after the
                first tick before cancelling the subscription.
            gateway: Optional pre-built gateway; if ``None`` a
                ``_NativeIBGateway`` is created from the connection parameters.
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.symbol_overrides = symbol_overrides or {}
        self.timeout_sec = timeout_sec
        self.use_rth = use_rth
        self.default_what_to_show = default_what_to_show.upper()
        self.l2_warmup_sec = l2_warmup_sec
        self._gateway: _IBGateway = gateway or _NativeIBGateway(
            host=host,
            port=port,
            client_id=client_id,
        )
        self._pacing_lock = Lock()
        self._request_times: List[float] = []
        self._identical_request_seen_at: Dict[str, float] = {}

    @property
    def name(self) -> str:
        """Return the provider name identifier."""
        return "ibkr-historical"

    @property
    def caps(self) -> Capabilities:
        """Return the capability flags for this provider."""
        return Capabilities(
            ohlcv_bars=True,
            l1_quotes=True,
            l2_books=True,
            trades=True,
            bid_ask_sizes=True,
            supports_adjusted_bars=True,
            max_symbols_per_request=50,
            max_l2_depth=10,
        )

    def close(self) -> None:
        """Disconnect from TWS / IB Gateway."""
        self._gateway.close()

    def get_ohlcv_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        interval: BarInterval,
        adjusted: bool = False,
    ) -> List[OHLCVBar]:
        """Fetch historical OHLCV bars for one or more symbols.

        Paginates backwards from ``end`` to ``start`` in chunks determined by
        ``_INTERVAL_TO_CHUNK_DURATION``, deduplicates overlapping bars, and
        returns the combined result sorted by ``(symbol, ts)``.

        Args:
            symbols: Iterable of ticker symbols (case-insensitive).
            start: Inclusive start of the requested window (UTC or naive).
            end: Exclusive end of the requested window (UTC or naive).
            interval: Bar granularity.
            adjusted: If ``True``, request split/dividend-adjusted prices.

        Returns:
            List of ``OHLCVBar`` objects sorted by ``(symbol, ts)``.

        Raises:
            ProviderError: If the time range is invalid, a symbol is empty, or
                the interval is unsupported.
            RateLimitError: If a local or IBKR pacing limit is exceeded.
        """
        self._ensure_connected()
        start_utc = self._as_utc(start)
        end_utc = self._as_utc(end)
        self._validate_time_range(start_utc, end_utc)

        bar_size = self._bar_size_for(interval)
        duration = self._duration_for(interval)
        step = _INTERVAL_STEP[interval]
        what_to_show = "ADJUSTED_LAST" if adjusted else self.default_what_to_show

        all_bars: List[OHLCVBar] = []
        for symbol in self._normalize_symbols(symbols):
            all_bars.extend(
                self._paginate_bars_for_symbol(
                    symbol, start_utc, end_utc, bar_size, duration, step, what_to_show, interval, adjusted
                )
            )

        return sorted(all_bars, key=lambda bar: (bar.symbol, bar.ts))

    def _paginate_bars_for_symbol(
        self,
        symbol: str,
        start_utc: datetime,
        end_utc: datetime,
        bar_size: str,
        duration: str,
        step: timedelta,
        what_to_show: str,
        interval: BarInterval,
        adjusted: bool,
    ) -> List[OHLCVBar]:
        """Fetch and deduplicate all bars for a single symbol over the full window.

        Iterates backwards from ``end_utc`` to ``start_utc``, calling
        ``_fetch_bars_chunk`` for each page, and collects unique bars (keyed by
        timestamp) in insertion order.

        Args:
            symbol: Normalised ticker symbol.
            start_utc: Inclusive start of the window (UTC).
            end_utc: Exclusive end of the window (UTC).
            bar_size: IBKR bar-size string.
            duration: IBKR duration string for each chunk.
            step: One bar's worth of time, used to advance the cursor.
            what_to_show: Data type passed to IBKR.
            interval: Bar granularity (stored on returned ``OHLCVBar``).
            adjusted: Whether adjusted prices were requested.

        Returns:
            List of ``OHLCVBar`` objects sorted by ``ts``.
        """
        bars_by_ts: Dict[datetime, OHLCVBar] = {}
        cursor = end_utc

        for _ in range(512):
            if cursor <= start_utc:
                break

            raw_bars = self._fetch_bars_chunk(
                symbol, cursor, bar_size, duration, what_to_show
            )
            if not raw_bars:
                break

            earliest_seen = cursor
            for raw in raw_bars:
                ts = self._as_utc(raw.ts)
                if ts < earliest_seen:
                    earliest_seen = ts
                if start_utc <= ts < end_utc:
                    bars_by_ts[ts] = OHLCVBar(
                        ts=ts,
                        open=float(raw.open),
                        high=float(raw.high),
                        low=float(raw.low),
                        close=float(raw.close),
                        volume=float(raw.volume),
                        symbol=symbol,
                        interval=interval,
                        source=self.name,
                        adjusted=adjusted,
                    )

            next_cursor = earliest_seen - step
            if next_cursor >= cursor:
                break
            cursor = next_cursor

        return sorted(bars_by_ts.values(), key=lambda bar: bar.ts)

    def _fetch_bars_chunk(
        self,
        symbol: str,
        cursor: datetime,
        bar_size: str,
        duration: str,
        what_to_show: str,
    ) -> List[_RawBar]:
        """Request a single chunk of historical bars from the gateway.

        Builds the pace key and delegates to ``_call_gateway``.

        Args:
            symbol: Normalised ticker symbol.
            cursor: End datetime for this chunk (passed as ``end_datetime``).
            bar_size: IBKR bar-size string.
            duration: IBKR duration string.
            what_to_show: Data type passed to IBKR.

        Returns:
            List of raw bars from the gateway.
        """
        end_dt_str = self._format_ib_datetime(cursor)
        return self._call_gateway(
            self._gateway.request_historical_bars,
            self._build_contract(symbol),
            _pace_key=f"bars:{symbol}:{bar_size}:{what_to_show}:{duration}:{self.use_rth}:{end_dt_str}",
            end_datetime=end_dt_str,
            duration_string=duration,
            bar_size=bar_size,
            what_to_show=what_to_show,
            use_rth=self.use_rth,
            timeout_sec=self.timeout_sec,
        )

    def get_l1_quotes(self, symbols: Iterable[str]) -> List[L1Quote]:
        """Fetch current L1 (top-of-book) quotes for one or more symbols.

        Args:
            symbols: Iterable of ticker symbols (case-insensitive).

        Returns:
            List of ``L1Quote`` objects, one per symbol, in input order.

        Raises:
            ProviderError: If a symbol is empty or the gateway returns an error.
            RateLimitError: If a local or IBKR pacing limit is exceeded.
        """
        self._ensure_connected()
        quotes: List[L1Quote] = []
        for symbol in self._normalize_symbols(symbols):
            raw = self._call_gateway(
                self._gateway.request_l1_snapshot,
                self._build_contract(symbol),
                _pace_key=f"l1:{symbol}",
                timeout_sec=self.timeout_sec,
            )
            quotes.append(
                L1Quote(
                    ts=self._as_utc(raw.ts),
                    symbol=symbol,
                    bid=raw.bid,
                    bid_size=raw.bid_size,
                    ask=raw.ask,
                    ask_size=raw.ask_size,
                    last=raw.last,
                    source=self.name,
                    venue=raw.venue,
                )
            )
        return quotes

    def get_trade_prints(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> List[TradePrint]:
        """Fetch historical trade ticks for one or more symbols.

        Paginates forwards from ``start`` to ``end`` in batches of up to
        1 000 ticks, deduplicates across overlapping batches, and returns the
        combined result sorted by ``(symbol, ts)``.

        Args:
            symbols: Iterable of ticker symbols (case-insensitive).
            start: Inclusive start of the requested window (UTC or naive).
            end: Exclusive end of the requested window (UTC or naive).

        Returns:
            List of ``TradePrint`` objects sorted by ``(symbol, ts)``.

        Raises:
            ProviderError: If the time range is invalid or a symbol is empty.
            RateLimitError: If a local or IBKR pacing limit is exceeded.
        """
        self._ensure_connected()
        start_utc = self._as_utc(start)
        end_utc = self._as_utc(end)
        self._validate_time_range(start_utc, end_utc)

        all_trades: List[TradePrint] = []
        for symbol in self._normalize_symbols(symbols):
            all_trades.extend(
                self._paginate_trades_for_symbol(symbol, start_utc, end_utc)
            )

        return sorted(all_trades, key=lambda t: (t.symbol, t.ts))

    def _paginate_trades_for_symbol(
        self,
        symbol: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[TradePrint]:
        """Fetch and deduplicate all trade ticks for a single symbol.

        Iterates forwards from ``start_utc`` to ``end_utc``, calling
        ``_fetch_trades_chunk`` for each page, and deduplicates using a
        ``(ts, price, size, venue, trade_id)`` key.

        Args:
            symbol: Normalised ticker symbol.
            start_utc: Inclusive start of the window (UTC).
            end_utc: Exclusive end of the window (UTC).

        Returns:
            List of ``TradePrint`` objects in no guaranteed order (caller sorts).
        """
        deduped: Dict[Tuple[datetime, float, float, Optional[str], Optional[str]], TradePrint] = {}
        cursor = start_utc

        for _ in range(512):
            if cursor >= end_utc:
                break

            batch = self._fetch_trades_chunk(symbol, cursor)
            if not batch:
                break

            latest = cursor
            for raw in sorted(batch, key=lambda t: t.ts):
                ts = self._as_utc(raw.ts)
                if ts > latest:
                    latest = ts
                if not (start_utc <= ts < end_utc):
                    continue
                key = (ts, raw.price, raw.size, raw.venue, raw.trade_id)
                deduped[key] = TradePrint(
                    ts=ts,
                    symbol=symbol,
                    price=float(raw.price),
                    size=float(raw.size),
                    source=self.name,
                    trade_id=raw.trade_id,
                    conditions=raw.conditions,
                    venue=raw.venue,
                )

            if len(batch) < 1000:
                break

            next_cursor = latest + timedelta(seconds=1)
            if next_cursor <= cursor:
                break
            cursor = next_cursor

        return list(deduped.values())

    def _fetch_trades_chunk(
        self,
        symbol: str,
        cursor: datetime,
    ) -> List[_RawTrade]:
        """Request a single batch of historical trade ticks from the gateway.

        Args:
            symbol: Normalised ticker symbol.
            cursor: Start datetime for this batch.

        Returns:
            List of raw trade ticks (up to 1 000).
        """
        return self._call_gateway(
            self._gateway.request_historical_trades,
            self._build_contract(symbol),
            _pace_key=f"trades:{symbol}:{self._format_ib_datetime(cursor)}:{self.use_rth}",
            start_datetime=self._format_ib_datetime(cursor),
            number_of_ticks=1000,
            use_rth=self.use_rth,
            timeout_sec=self.timeout_sec,
        )

    def get_l2_order_books(
        self,
        symbols: Iterable[str],
        depth: Optional[int] = None,
    ) -> List[L2OrderBookSnapshot]:
        """Fetch L2 order-book snapshots for one or more symbols.

        Args:
            symbols: Iterable of ticker symbols (case-insensitive).
            depth: Number of price levels to request per side (default 5).

        Returns:
            List of ``L2OrderBookSnapshot`` objects, one per symbol.

        Raises:
            ProviderError: If ``depth`` is invalid or a symbol is empty.
            RateLimitError: If a local or IBKR pacing limit is exceeded.
        """
        self._ensure_connected()
        requested_depth = depth or 5
        if requested_depth <= 0:
            raise ProviderError("depth must be a positive integer")
        if self.caps.max_l2_depth is not None and requested_depth > self.caps.max_l2_depth:
            raise ProviderError(
                f"depth {requested_depth} exceeds max supported depth {self.caps.max_l2_depth}"
            )

        books: List[L2OrderBookSnapshot] = []
        for symbol in self._normalize_symbols(symbols):
            raw = self._call_gateway(
                self._gateway.request_l2_snapshot,
                self._build_contract(symbol),
                _pace_key=f"l2:{symbol}:{requested_depth}",
                depth=requested_depth,
                warmup_sec=self.l2_warmup_sec,
                timeout_sec=self.timeout_sec,
            )

            bids = tuple(
                PriceLevel(price=price, size=size)
                for price, size in sorted(raw.bids, key=lambda level: level[0], reverse=True)
            )
            asks = tuple(
                PriceLevel(price=price, size=size)
                for price, size in sorted(raw.asks, key=lambda level: level[0])
            )
            books.append(
                L2OrderBookSnapshot(
                    ts=self._as_utc(raw.ts),
                    symbol=symbol,
                    bids=bids,
                    asks=asks,
                    source=self.name,
                    depth=requested_depth,
                    venue=raw.venue,
                )
            )
        return books

    def _ensure_connected(self) -> None:
        """Ensure the underlying gateway is connected, connecting if needed."""
        self._call_gateway(self._gateway.connect)

    def _call_gateway(self, func, *args, _pace_key: Optional[str] = None, **kwargs):
        """Call a gateway function, enforcing pacing and mapping errors.

        Args:
            func: Gateway callable to invoke.
            *args: Positional arguments forwarded to ``func``.
            _pace_key: If provided, the pacing guard is checked and updated
                for this key before calling ``func``.
            **kwargs: Keyword arguments forwarded to ``func``.

        Returns:
            Whatever ``func`` returns.

        Raises:
            RateLimitError: If a pacing limit is exceeded (local or IBKR).
            ProviderError: For any other IBKR error.
        """
        if _pace_key is not None:
            self._enforce_local_pacing(_pace_key)
        try:
            return func(*args, **kwargs)
        except _IBGatewayError as exc:
            message = exc.message.lower()
            if exc.code in _PACED_ERROR_CODES or "pacing violation" in message:
                raise RateLimitError(f"IBKR pacing limit hit: {exc.message}") from exc
            raise ProviderError(f"IBKR error: {exc.message}") from exc

    def _enforce_local_pacing(self, request_key: str) -> None:
        """Apply IBKR's published pacing rules before issuing a request.

        Rules enforced:
        - No more than 60 requests in any rolling 10-minute window.
        - Identical requests (same key) must be at least 15 seconds apart.

        Args:
            request_key: Opaque string that uniquely identifies the request
                parameters; used for the identical-request check.

        Raises:
            RateLimitError: If either pacing rule would be violated.
        """
        now = time.monotonic()
        with self._pacing_lock:
            self._request_times = [t for t in self._request_times if (now - t) < 600.0]
            if len(self._request_times) >= 60:
                raise RateLimitError("local pacing guard: >60 IBKR requests in 10 minutes")

            last_seen = self._identical_request_seen_at.get(request_key)
            if last_seen is not None and (now - last_seen) < 15.0:
                raise RateLimitError("local pacing guard: identical IBKR request within 15 seconds")

            self._identical_request_seen_at[request_key] = now
            self._request_times.append(now)

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
        """Build an IB contract dict for ``symbol``, applying any overrides.

        Args:
            symbol: Normalised (upper-cased) ticker symbol.

        Returns:
            Contract specification dict suitable for passing to gateway methods.
        """
        override = self.symbol_overrides.get(symbol) or self.symbol_overrides.get(symbol.upper()) or {}
        contract: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "secType": "STK",
            "exchange": "SMART",
            "currency": "USD",
        }
        contract.update(override)
        return contract

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

    @staticmethod
    def _validate_time_range(start: datetime, end: datetime) -> None:
        """Assert that ``start`` is strictly before ``end``.

        Args:
            start: Start of the window (UTC).
            end: End of the window (UTC).

        Raises:
            ProviderError: If ``start >= end``.
        """
        if start >= end:
            raise ProviderError("start must be before end")

    @staticmethod
    def _format_ib_datetime(ts: datetime) -> str:
        """Format a datetime as the ``YYYYMMDD-HH:MM:SS`` string IBKR expects.

        Args:
            ts: Datetime to format (converted to UTC before formatting).

        Returns:
            String in ``YYYYMMDD-HH:MM:SS`` format.
        """
        return ts.astimezone(timezone.utc).strftime("%Y%m%d-%H:%M:%S")

    @staticmethod
    def _bar_size_for(interval: BarInterval) -> str:
        """Return the IBKR bar-size string for ``interval``.

        Args:
            interval: The desired bar granularity.

        Returns:
            IBKR bar-size string (e.g. ``"1 min"``).

        Raises:
            ProviderError: If ``interval`` is not in ``_INTERVAL_TO_BAR_SIZE``.
        """
        try:
            return _INTERVAL_TO_BAR_SIZE[interval]
        except KeyError as exc:
            raise ProviderError(f"unsupported interval: {interval}") from exc

    @staticmethod
    def _duration_for(interval: BarInterval) -> str:
        """Return the IBKR chunk-duration string for ``interval``.

        Args:
            interval: The desired bar granularity.

        Returns:
            IBKR duration string (e.g. ``"1 D"``).

        Raises:
            ProviderError: If ``interval`` is not in ``_INTERVAL_TO_CHUNK_DURATION``.
        """
        try:
            return _INTERVAL_TO_CHUNK_DURATION[interval]
        except KeyError as exc:
            raise ProviderError(f"unsupported interval: {interval}") from exc


# ---------------------------------------------------------------------------
# _NativeIBGateway
# ---------------------------------------------------------------------------

