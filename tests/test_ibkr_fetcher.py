from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research.fetchers.base import ProviderError, RateLimitError
from research.fetchers.models import BarInterval
from research.fetchers.providers.ibkr import (
    IBKRHistoricalFetcher,
    _IBGatewayError,
    _RawBar,
    _RawBook,
    _RawQuote,
    _RawTrade,
)


class FakeGateway:
    def __init__(self):
        self.connected = False
        self.calls = []
        self._bar_batches = {}
        self._trade_batches = {}
        self._quotes = {}
        self._books = {}

    def connect(self):
        self.connected = True
        self.calls.append(("connect",))

    def close(self):
        self.connected = False
        self.calls.append(("close",))

    def request_historical_bars(
        self,
        contract,
        *,
        end_datetime,
        duration_string,
        bar_size,
        what_to_show,
        use_rth,
        timeout_sec,
    ):
        symbol = contract["symbol"]
        self.calls.append(
            (
                "bars",
                symbol,
                end_datetime,
                duration_string,
                bar_size,
                what_to_show,
                use_rth,
                timeout_sec,
                dict(contract),
            )
        )
        batches = self._bar_batches.get(symbol, [])
        if not batches:
            return []
        return batches.pop(0)

    def request_l1_snapshot(self, contract, *, timeout_sec):
        symbol = contract["symbol"]
        self.calls.append(("l1", symbol, timeout_sec, dict(contract)))
        return self._quotes[symbol]

    def request_historical_trades(
        self,
        contract,
        *,
        start_datetime,
        number_of_ticks,
        use_rth,
        timeout_sec,
    ):
        symbol = contract["symbol"]
        self.calls.append(
            ("trades", symbol, start_datetime, number_of_ticks, use_rth, timeout_sec)
        )
        batches = self._trade_batches.get(symbol, [])
        if not batches:
            return []
        return batches.pop(0)

    def request_l2_snapshot(self, contract, *, depth, warmup_sec, timeout_sec):
        symbol = contract["symbol"]
        self.calls.append(("l2", symbol, depth, warmup_sec, timeout_sec))
        return self._books[symbol]


def _dt(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2024, 1, 2, hour, minute, second, tzinfo=timezone.utc)


def test_get_ohlcv_bars_adjusted_dedup_and_contract_defaults():
    gateway = FakeGateway()
    gateway._bar_batches["AAPL"] = [
        [
            _RawBar(ts=_dt(10, 0), open=1, high=2, low=0.5, close=1.5, volume=100),
            _RawBar(ts=_dt(10, 1), open=2, high=3, low=1.5, close=2.5, volume=200),
            _RawBar(ts=_dt(10, 2), open=3, high=4, low=2.5, close=3.5, volume=300),
        ],
        [
            _RawBar(ts=_dt(9, 59), open=0.9, high=1.1, low=0.8, close=1.0, volume=50),
            _RawBar(ts=_dt(10, 0), open=1, high=2, low=0.5, close=1.5, volume=100),
        ],
    ]
    fetcher = IBKRHistoricalFetcher(gateway=gateway, timeout_sec=5.0)

    bars = fetcher.get_ohlcv_bars(
        symbols=["aapl"],
        start=_dt(10, 0),
        end=_dt(10, 3),
        interval=BarInterval.MIN_1,
        adjusted=True,
    )

    assert len(bars) == 3
    assert [b.ts for b in bars] == [_dt(10, 0), _dt(10, 1), _dt(10, 2)]
    assert all(b.adjusted is True for b in bars)
    assert all(b.symbol == "AAPL" for b in bars)

    bar_calls = [call for call in gateway.calls if call[0] == "bars"]
    assert bar_calls[0][3] == "1 D"
    assert bar_calls[0][4] == "1 min"
    assert bar_calls[0][5] == "ADJUSTED_LAST"
    assert bar_calls[0][8]["secType"] == "STK"
    assert bar_calls[0][8]["exchange"] == "SMART"
    assert bar_calls[0][8]["currency"] == "USD"


def test_get_l1_quotes_with_symbol_override():
    gateway = FakeGateway()
    gateway._quotes["BTC"] = _RawQuote(
        ts=_dt(11, 0),
        bid=100.0,
        ask=101.0,
        bid_size=1.5,
        ask_size=1.7,
        last=100.5,
        venue="PAXOS",
    )
    fetcher = IBKRHistoricalFetcher(
        gateway=gateway,
        symbol_overrides={"BTC": {"secType": "CRYPTO", "exchange": "PAXOS", "currency": "USD"}},
    )

    quotes = fetcher.get_l1_quotes(["btc"])
    assert len(quotes) == 1
    assert quotes[0].symbol == "BTC"
    assert quotes[0].bid == 100.0
    assert quotes[0].ask_size == 1.7
    assert quotes[0].venue == "PAXOS"

    call = [c for c in gateway.calls if c[0] == "l1"][0]
    assert call[3]["secType"] == "CRYPTO"
    assert call[3]["exchange"] == "PAXOS"


def test_get_trade_prints_paginates_batches():
    gateway = FakeGateway()
    start = _dt(12, 0)
    first_batch = [
        _RawTrade(
            ts=start + timedelta(seconds=i),
            price=100.0 + i,
            size=1.0,
            venue="NYSE",
            conditions=None,
            trade_id=str(i),
        )
        for i in range(1000)
    ]
    second_batch = [
        _RawTrade(
            ts=start + timedelta(seconds=1000),
            price=1100.0,
            size=2.0,
            venue="NYSE",
            conditions=("@",),
            trade_id="1000",
        ),
        _RawTrade(
            ts=start + timedelta(seconds=1001),
            price=1101.0,
            size=3.0,
            venue="NYSE",
            conditions=None,
            trade_id="1001",
        ),
    ]
    gateway._trade_batches["AAPL"] = [first_batch, second_batch]
    fetcher = IBKRHistoricalFetcher(gateway=gateway)

    trades = fetcher.get_trade_prints(
        symbols=["AAPL"],
        start=start,
        end=start + timedelta(seconds=1002),
    )

    assert len(trades) == 1002
    assert trades[0].trade_id == "0"
    assert trades[-1].trade_id == "1001"

    trade_calls = [call for call in gateway.calls if call[0] == "trades"]
    assert len(trade_calls) == 2
    assert trade_calls[0][2] == "20240102-12:00:00"
    assert trade_calls[1][2] == "20240102-12:16:40"


def test_get_l2_order_books_sorts_levels_and_enforces_depth():
    gateway = FakeGateway()
    gateway._books["AAPL"] = _RawBook(
        ts=_dt(13, 0),
        bids=((100.0, 3.0), (101.0, 1.0)),
        asks=((103.0, 2.0), (102.0, 4.0)),
        venue=None,
    )
    fetcher = IBKRHistoricalFetcher(gateway=gateway)

    books = fetcher.get_l2_order_books(["AAPL"], depth=2)
    assert len(books) == 1
    assert books[0].bids[0].price == 101.0
    assert books[0].bids[1].price == 100.0
    assert books[0].asks[0].price == 102.0
    assert books[0].asks[1].price == 103.0

    with pytest.raises(ProviderError):
        fetcher.get_l2_order_books(["AAPL"], depth=99)


def test_maps_pacing_errors_to_rate_limit():
    gateway = FakeGateway()

    def _raise(*args, **kwargs):
        raise _IBGatewayError("Pacing violation", code=162)

    gateway.request_l1_snapshot = _raise
    fetcher = IBKRHistoricalFetcher(gateway=gateway)

    with pytest.raises(RateLimitError):
        fetcher.get_l1_quotes(["AAPL"])
