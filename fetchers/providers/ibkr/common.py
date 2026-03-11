from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Event
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from ...models import BarInterval

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_INTERVAL_TO_BAR_SIZE: Dict[BarInterval, str] = {
    BarInterval.MIN_1: "1 min",
    BarInterval.MIN_5: "5 mins",
    BarInterval.HOUR_1: "1 hour",
    BarInterval.DAY_1: "1 day",
}
"""Mapping from ``BarInterval`` to the IB API bar-size string."""

_INTERVAL_TO_CHUNK_DURATION: Dict[BarInterval, str] = {
    BarInterval.MIN_1: "1 D",
    BarInterval.MIN_5: "1 W",
    BarInterval.HOUR_1: "1 M",
    BarInterval.DAY_1: "1 Y",
}
"""Maximum duration string that IBKR accepts for each bar interval."""

_INTERVAL_STEP: Dict[BarInterval, timedelta] = {
    BarInterval.MIN_1: timedelta(minutes=1),
    BarInterval.MIN_5: timedelta(minutes=5),
    BarInterval.HOUR_1: timedelta(hours=1),
    BarInterval.DAY_1: timedelta(days=1),
}
"""One bar's worth of time for each interval, used to step the pagination cursor."""

_PACED_ERROR_CODES = {162, 420}
"""IBKR error codes that indicate a pacing violation."""


# ---------------------------------------------------------------------------
# Internal raw data-transfer objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _RawBar:
    """Raw OHLCV bar as returned by the IB gateway before model conversion."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class _RawQuote:
    """Raw L1 quote fields as returned by the IB gateway."""

    ts: datetime
    bid: Optional[float]
    ask: Optional[float]
    bid_size: Optional[float]
    ask_size: Optional[float]
    last: Optional[float]
    venue: Optional[str]


@dataclass(frozen=True, slots=True)
class _RawTrade:
    """Raw trade-tick fields as returned by the IB gateway."""

    ts: datetime
    price: float
    size: float
    venue: Optional[str]
    conditions: Optional[Tuple[str, ...]]
    trade_id: Optional[str]


@dataclass(frozen=True, slots=True)
class _RawBook:
    """Raw order-book snapshot as returned by the IB gateway."""

    ts: datetime
    bids: Tuple[Tuple[float, float], ...]
    asks: Tuple[Tuple[float, float], ...]
    venue: Optional[str]


# ---------------------------------------------------------------------------
# Gateway error and protocol
# ---------------------------------------------------------------------------

class _IBGatewayError(Exception):
    """Structured gateway error so the fetcher can map to project exceptions."""

    def __init__(self, message: str, code: Optional[int] = None):
        """Initialise the error.

        Args:
            message: Human-readable description of the error.
            code: Optional IBKR numeric error code.
        """
        super().__init__(message)
        self.code = code
        self.message = message


class _IBGateway(Protocol):
    """Gateway protocol used by IBKRHistoricalFetcher."""

    def connect(self) -> None:
        """Establish a connection to TWS / IB Gateway."""
        ...

    def close(self) -> None:
        """Disconnect and release resources."""
        ...

    def request_historical_bars(
        self,
        contract: Mapping[str, Any],
        *,
        end_datetime: str,
        duration_string: str,
        bar_size: str,
        what_to_show: str,
        use_rth: bool,
        timeout_sec: float,
    ) -> List[_RawBar]:
        """Fetch a single chunk of historical OHLCV bars.

        Args:
            contract: IB contract specification dict.
            end_datetime: End of the requested window (``YYYYMMDD-HH:MM:SS`` UTC).
            duration_string: IBKR duration string (e.g. ``"1 D"``).
            bar_size: IBKR bar-size string (e.g. ``"1 min"``).
            what_to_show: Data type (e.g. ``"TRADES"``).
            use_rth: Whether to limit data to regular trading hours.
            timeout_sec: Seconds to wait before raising a timeout error.

        Returns:
            List of raw bars in the requested window.
        """
        ...

    def request_l1_snapshot(
        self,
        contract: Mapping[str, Any],
        *,
        timeout_sec: float,
    ) -> _RawQuote:
        """Fetch a snapshot of the current L1 (top-of-book) quote.

        Args:
            contract: IB contract specification dict.
            timeout_sec: Seconds to wait before raising a timeout error.

        Returns:
            Raw L1 quote.
        """
        ...

    def request_historical_trades(
        self,
        contract: Mapping[str, Any],
        *,
        start_datetime: str,
        number_of_ticks: int,
        use_rth: bool,
        timeout_sec: float,
    ) -> List[_RawTrade]:
        """Fetch a batch of historical trade ticks.

        Args:
            contract: IB contract specification dict.
            start_datetime: Start of the requested window (``YYYYMMDD-HH:MM:SS`` UTC).
            number_of_ticks: Maximum ticks to return per call (up to 1 000).
            use_rth: Whether to limit data to regular trading hours.
            timeout_sec: Seconds to wait before raising a timeout error.

        Returns:
            List of raw trade ticks.
        """
        ...

    def request_l2_snapshot(
        self,
        contract: Mapping[str, Any],
        *,
        depth: int,
        warmup_sec: float,
        timeout_sec: float,
    ) -> _RawBook:
        """Fetch an L2 order-book snapshot.

        Args:
            contract: IB contract specification dict.
            depth: Number of price levels to request on each side.
            warmup_sec: Extra time to wait after the first update before
                cancelling the subscription, so the book can stabilise.
            timeout_sec: Seconds to wait for the first update.

        Returns:
            Raw order-book snapshot.
        """
        ...


# ---------------------------------------------------------------------------
# Per-request state containers used by _IBApp
# ---------------------------------------------------------------------------

@dataclass
class _BarsState:
    """Mutable state for a single historical-bars request."""

    event: Event
    """Set by ``historicalDataEnd`` when all bars have been received."""
    bars: List[_RawBar]
    """Accumulated bars, appended by ``historicalData``."""
    error: Optional[_IBGatewayError] = None
    """Populated by ``error`` if the gateway returns an error for this request."""


@dataclass
class _L1State:
    """Mutable state for a single L1 snapshot request."""

    event: Event
    """Set by ``tickSnapshotEnd`` when the snapshot is complete."""
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    last: Optional[float] = None
    ts: Optional[datetime] = None
    """Timestamp of the most recent tick update."""
    error: Optional[_IBGatewayError] = None


@dataclass
class _TradesState:
    """Mutable state for a single historical-trades request."""

    event: Event
    """Set by ``historicalTicksLast`` when ``done`` is ``True``."""
    trades: List[_RawTrade]
    """Accumulated trade ticks."""
    error: Optional[_IBGatewayError] = None


@dataclass
class _L2State:
    """Mutable state for a single L2 depth-of-market subscription."""

    ready_event: Event
    """Set on the first ``updateMktDepth`` callback."""
    bids: Dict[int, Tuple[float, float]]
    """Price-level index → (price, size) for the bid side."""
    asks: Dict[int, Tuple[float, float]]
    """Price-level index → (price, size) for the ask side."""
    ts: Optional[datetime] = None
    """Timestamp of the most recent depth update."""
    error: Optional[_IBGatewayError] = None


@dataclass
class _OrderState:
    """Mutable state for a single market-order placement."""

    event: Event
    """Set by ``orderStatus`` when a terminal or acknowledged status is received."""
    status: str = ""
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    error: Optional[_IBGatewayError] = None


# NOTE: The concrete _IBApp class (EWrapper / EClient subclass) is defined
# inside _NativeIBGateway._build_app so that ibapi is only imported at
# connection time, keeping this module importable without ibapi installed.

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _parse_ib_timestamp(value: Any) -> datetime:
    """Parse an IB timestamp value into a UTC-aware ``datetime``.

    IBKR returns timestamps in several formats depending on bar size and
    context:

    - Unix epoch integer or float.
    - Eight-digit decimal string ``YYYYMMDD`` (daily bars).
    - Numeric string of a Unix epoch.
    - ``YYYYMMDD-HH:MM:SS`` string.
    - ``YYYYMMDD HH:MM:SS`` string (space separator).

    Args:
        value: Raw timestamp value from the IB API (``bar.date`` etc.).

    Returns:
        UTC-aware ``datetime`` corresponding to ``value``.
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        if len(text) == 8:
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        return datetime.fromtimestamp(int(text), tz=timezone.utc)
    if "-" in text:
        return datetime.strptime(text, "%Y%m%d-%H:%M:%S").replace(tzinfo=timezone.utc)
    if " " in text:
        return datetime.strptime(text, "%Y%m%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)


def _apply_depth_op(
    book: Dict[int, Tuple[float, float]],
    position: int,
    operation: int,
    price: float,
    size: float,
) -> None:
    """Apply a single IBKR market-depth operation to a price-level dict.

    Operation codes (per ibapi spec):
    - 0: insert
    - 1: update
    - 2: delete

    Args:
        book: Mutable dict mapping price-level index to ``(price, size)``.
        position: Price-level index (0 = best).
        operation: IBKR operation code (0=insert, 1=update, 2=delete).
        price: New price at this level.
        size: New size at this level.
    """
    if operation == 2:
        book.pop(position, None)
        return
    book[position] = (price, size)
