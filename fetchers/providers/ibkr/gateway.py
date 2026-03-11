from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Lock, Thread
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .common import (
    _BarsState,
    _IBGatewayError,
    _L1State,
    _L2State,
    _OrderState,
    _RawBar,
    _RawBook,
    _RawQuote,
    _RawTrade,
    _TradesState,
    _apply_depth_op,
    _parse_ib_timestamp,
)

class _NativeIBGateway:
    """Thin synchronous wrapper around the ibapi callback flow.

    Each public method:
    1. Allocates a unique request-ID.
    2. Registers a per-request state object with ``_IBApp``.
    3. Issues the corresponding ``EClient`` call.
    4. Blocks on ``threading.Event.wait`` until the matching ``EWrapper``
       callback signals completion (or a timeout fires).
    5. Raises ``_IBGatewayError`` on timeout or if the state object holds an
       error.
    """

    def __init__(self, *, host: str, port: int, client_id: int):
        """Initialise connection parameters without connecting.

        Args:
            host: Hostname of the TWS / IB Gateway process.
            port: TCP port number.
            client_id: Unique client-ID for this session.
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self._connected = False
        self._connect_lock = Lock()
        self._req_id_lock = Lock()
        self._next_req_id = 10_000
        self._thread: Optional[Thread] = None
        self._app = None

    def connect(self) -> None:
        """Connect to TWS / IB Gateway if not already connected.

        Starts the EClient message-loop thread and waits up to 5 seconds for
        ``EClient.isConnected()`` to become ``True``.

        Raises:
            _IBGatewayError: If the connection cannot be established within
                5 seconds.
        """
        with self._connect_lock:
            if self._connected:
                return
            app = self._build_app()
            app.connect(self.host, self.port, self.client_id)
            thread = Thread(target=app.run, daemon=True)
            thread.start()

            deadline = time.time() + 5.0
            while time.time() < deadline:
                if app.isConnected():
                    self._app = app
                    self._thread = thread
                    self._connected = True
                    return
                time.sleep(0.05)
            raise _IBGatewayError("unable to connect to TWS/IB Gateway")

    def close(self) -> None:
        """Disconnect from TWS / IB Gateway and release resources."""
        with self._connect_lock:
            if not self._connected:
                return
            assert self._app is not None
            self._app.disconnect()
            self._connected = False
            self._app = None
            self._thread = None

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
            List of ``_RawBar`` objects for the requested window.

        Raises:
            _IBGatewayError: On timeout or if IBKR returns an error.
        """
        app = self._require_app()
        req_id = self._alloc_req_id()
        state = app.init_historical_bars(req_id)
        app.reqHistoricalData(
            req_id,
            self._to_contract(contract),
            end_datetime,
            duration_string,
            bar_size,
            what_to_show,
            int(use_rth),
            2,
            False,
            [],
        )
        self._wait_for_state(state.event, timeout_sec, req_id, "historical bars")
        if state.error is not None:
            raise state.error
        return list(state.bars)

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
            ``_RawQuote`` with the current bid, ask, and last price.

        Raises:
            _IBGatewayError: On timeout or if IBKR returns an error.
        """
        app = self._require_app()
        req_id = self._alloc_req_id()
        state = app.init_l1_snapshot(req_id)
        app.reqMktData(req_id, self._to_contract(contract), "", True, False, [])
        self._wait_for_state(state.event, timeout_sec, req_id, "l1 snapshot")
        app.cancelMktData(req_id)
        if state.error is not None:
            raise state.error
        ts = state.ts or datetime.now(tz=timezone.utc)
        return _RawQuote(
            ts=ts,
            bid=state.bid,
            ask=state.ask,
            bid_size=state.bid_size,
            ask_size=state.ask_size,
            last=state.last,
            venue=None,
        )

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
            List of ``_RawTrade`` objects.

        Raises:
            _IBGatewayError: On timeout or if IBKR returns an error.
        """
        app = self._require_app()
        req_id = self._alloc_req_id()
        state = app.init_historical_trades(req_id)
        app.reqHistoricalTicks(
            req_id,
            self._to_contract(contract),
            start_datetime,
            "",
            number_of_ticks,
            "TRADES",
            int(use_rth),
            False,
            [],
        )
        self._wait_for_state(state.event, timeout_sec, req_id, "historical trades")
        if state.error is not None:
            raise state.error
        return list(state.trades)

    def request_l2_snapshot(
        self,
        contract: Mapping[str, Any],
        *,
        depth: int,
        warmup_sec: float,
        timeout_sec: float,
    ) -> _RawBook:
        """Fetch an L2 order-book snapshot.

        Subscribes to market depth, waits for the first update, sleeps for
        ``warmup_sec`` to let the book stabilise, then cancels the subscription.

        Args:
            contract: IB contract specification dict.
            depth: Number of price levels to request on each side.
            warmup_sec: Extra seconds to wait after the first update.
            timeout_sec: Seconds to wait for the first update.

        Returns:
            ``_RawBook`` with bids and asks at the time of cancellation.

        Raises:
            _IBGatewayError: If IBKR returns an error for this request.
        """
        app = self._require_app()
        req_id = self._alloc_req_id()
        state = app.init_l2_snapshot(req_id)
        app.reqMktDepth(req_id, self._to_contract(contract), depth, False, [])

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if state.ready_event.is_set():
                break
            time.sleep(0.05)
        time.sleep(max(0.0, warmup_sec))
        try:
            app.cancelMktDepth(req_id, False)
        except TypeError:
            app.cancelMktDepth(req_id)
        if state.error is not None:
            raise state.error
        return _RawBook(
            ts=state.ts or datetime.now(tz=timezone.utc),
            bids=tuple(state.bids.values()),
            asks=tuple(state.asks.values()),
            venue=None,
        )

    def get_next_order_id(self, timeout_sec: float = 5.0) -> int:
        """Return the next valid order-ID, waiting for IBKR to provide one.

        Args:
            timeout_sec: Seconds to wait for ``nextValidId`` to fire.

        Returns:
            A unique order ID suitable for use with ``placeOrder``.

        Raises:
            _IBGatewayError: If the order-ID is not received within ``timeout_sec``.
        """
        app = self._require_app()
        if not app._order_id_ready.wait(timeout=timeout_sec):
            raise _IBGatewayError("timeout waiting for next valid order ID")
        with self._req_id_lock:
            order_id = app._next_order_id
            app._next_order_id += 1
            return order_id

    def place_market_order(
        self,
        contract: Mapping[str, Any],
        qty: int,
        action: str,
        timeout_sec: float = 30.0,
    ) -> Tuple[float, float]:
        """Place a market order. Returns (avg_fill_price, filled_qty).

        Args:
            contract: IB contract specification dict.
            qty: Absolute quantity of shares/contracts.
            action: ``"BUY"`` or ``"SELL"``.
            timeout_sec: Seconds to wait for an acknowledged or filled status.

        Returns:
            Tuple of ``(avg_fill_price, filled_qty)``.

        Raises:
            _IBGatewayError: If ibapi is not installed, if the order-ID cannot
                be obtained, or if the order does not reach a terminal status
                within ``timeout_sec``.
        """
        try:
            from ibapi.order import Order as IBOrder
        except ModuleNotFoundError as exc:
            raise _IBGatewayError("ibapi package is required. Install with: pip install ibapi") from exc

        app = self._require_app()
        order_id = self.get_next_order_id()
        state = app.init_order(order_id)

        order = IBOrder()
        order.action = action.upper()
        order.orderType = "MKT"
        order.totalQuantity = abs(qty)

        app.placeOrder(order_id, self._to_contract(contract), order)
        self._wait_for_state(state.event, timeout_sec, order_id, "order fill")

        if state.error is not None:
            raise state.error
        return state.avg_fill_price, state.filled_qty

    def _require_app(self):
        """Return the connected ``_IBApp`` instance or raise.

        Returns:
            The live ``_IBApp`` object.

        Raises:
            _IBGatewayError: If the gateway is not connected.
        """
        if not self._connected or self._app is None:
            raise _IBGatewayError("gateway is not connected")
        return self._app

    def _alloc_req_id(self) -> int:
        """Allocate and return the next unique request-ID.

        Returns:
            Monotonically increasing integer starting from 10 001.
        """
        with self._req_id_lock:
            self._next_req_id += 1
            return self._next_req_id

    @staticmethod
    def _wait_for_state(event: Event, timeout_sec: float, req_id: int, label: str) -> None:
        """Block until ``event`` is set or ``timeout_sec`` elapses.

        Args:
            event: The ``threading.Event`` to wait on.
            timeout_sec: Maximum seconds to block.
            req_id: Request or order ID, used in the timeout error message.
            label: Human-readable description of what is being waited for.

        Raises:
            _IBGatewayError: If the event is not set within ``timeout_sec``.
        """
        if not event.wait(timeout=timeout_sec):
            raise _IBGatewayError(f"timeout waiting for {label} (reqId={req_id})")

    @staticmethod
    def _to_contract(spec: Mapping[str, Any]):
        """Instantiate an ibapi ``Contract`` object from a spec dict.

        Args:
            spec: Mapping whose keys correspond to ``Contract`` attributes.

        Returns:
            A populated ``ibapi.contract.Contract`` instance.

        Raises:
            _IBGatewayError: If the ibapi package is not installed.
        """
        try:
            from ibapi.contract import Contract
        except ModuleNotFoundError as exc:
            raise _IBGatewayError(
                "ibapi package is required. Install with: pip install ibapi"
            ) from exc

        contract = Contract()
        for key, value in spec.items():
            setattr(contract, key, value)
        return contract

    def _build_app(self):
        """Dynamically construct and return a connected ``_IBApp`` instance.

        Imports ``EWrapper`` and ``EClient`` at call time so the module can be
        imported without ibapi installed.

        Returns:
            A fresh ``_IBApp`` (``EWrapper`` / ``EClient`` subclass) instance.

        Raises:
            _IBGatewayError: If the ibapi package is not installed.
        """
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ModuleNotFoundError as exc:
            raise _IBGatewayError(
                "ibapi package is required. Install with: pip install ibapi"
            ) from exc

        class _IBApp(EWrapper, EClient):
            """Concrete EWrapper / EClient implementation.

            Maintains per-request state dicts (``_bars``, ``_quotes``,
            ``_trades``, ``_depth``, ``_orders``) and implements the EWrapper
            callbacks that populate those state objects and signal completion.
            """

            def __init__(self):
                """Initialise ibapi base classes and per-request state dicts."""
                EWrapper.__init__(self)
                EClient.__init__(self, self)
                self._bars: Dict[int, _BarsState] = {}
                self._quotes: Dict[int, _L1State] = {}
                self._trades: Dict[int, _TradesState] = {}
                self._depth: Dict[int, _L2State] = {}
                self._orders: Dict[int, _OrderState] = {}
                self._next_order_id: int = 0
                self._order_id_ready: Event = Event()

            def init_historical_bars(self, req_id: int) -> _BarsState:
                """Register a new ``_BarsState`` for ``req_id`` and return it."""
                state = _BarsState(event=Event(), bars=[])
                self._bars[req_id] = state
                return state

            def init_l1_snapshot(self, req_id: int) -> _L1State:
                """Register a new ``_L1State`` for ``req_id`` and return it."""
                state = _L1State(event=Event())
                self._quotes[req_id] = state
                return state

            def init_historical_trades(self, req_id: int) -> _TradesState:
                """Register a new ``_TradesState`` for ``req_id`` and return it."""
                state = _TradesState(event=Event(), trades=[])
                self._trades[req_id] = state
                return state

            def init_l2_snapshot(self, req_id: int) -> _L2State:
                """Register a new ``_L2State`` for ``req_id`` and return it."""
                state = _L2State(ready_event=Event(), bids={}, asks={})
                self._depth[req_id] = state
                return state

            def init_order(self, order_id: int) -> _OrderState:
                """Register a new ``_OrderState`` for ``order_id`` and return it."""
                state = _OrderState(event=Event())
                self._orders[order_id] = state
                return state

            def nextValidId(self, orderId: int) -> None:
                """EWrapper callback: store the first valid order-ID and signal readiness."""
                self._next_order_id = orderId
                self._order_id_ready.set()

            def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, *_) -> None:  # noqa: ARG002
                """EWrapper callback: update order state and signal on terminal statuses."""
                state = self._orders.get(orderId)
                if state is None:
                    return
                state.status = status
                state.filled_qty = float(filled)
                if avgFillPrice:
                    state.avg_fill_price = float(avgFillPrice)
                if status in ("Filled", "Submitted", "PreSubmitted", "Inactive"):
                    state.event.set()

            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
                """EWrapper callback: propagate errors to the relevant state object."""
                message = f"[{errorCode}] {errorString}"
                err = _IBGatewayError(message, code=errorCode)
                if reqId in self._bars:
                    self._bars[reqId].error = err
                    self._bars[reqId].event.set()
                if reqId in self._quotes:
                    self._quotes[reqId].error = err
                    self._quotes[reqId].event.set()
                if reqId in self._trades:
                    self._trades[reqId].error = err
                    self._trades[reqId].event.set()
                if reqId in self._depth:
                    self._depth[reqId].error = err
                    self._depth[reqId].ready_event.set()

            def historicalData(self, reqId, bar):
                """EWrapper callback: append a single bar to the bars state."""
                state = self._bars.get(reqId)
                if state is None:
                    return
                state.bars.append(
                    _RawBar(
                        ts=_parse_ib_timestamp(bar.date),
                        open=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        close=float(bar.close),
                        volume=float(bar.volume),
                    )
                )

            def historicalDataEnd(self, reqId, startDate, endDate):
                """EWrapper callback: signal that all bars have been received."""
                state = self._bars.get(reqId)
                if state is not None:
                    state.event.set()

            def tickPrice(self, reqId, tickType, price, attrib):
                """EWrapper callback: update bid, ask, or last price in L1 state."""
                state = self._quotes.get(reqId)
                if state is None:
                    return
                if tickType == 1:
                    state.bid = float(price)
                elif tickType == 2:
                    state.ask = float(price)
                elif tickType == 4:
                    state.last = float(price)
                state.ts = datetime.now(tz=timezone.utc)

            def tickSize(self, reqId, tickType, size):
                """EWrapper callback: update bid-size or ask-size in L1 state."""
                state = self._quotes.get(reqId)
                if state is None:
                    return
                if tickType == 0:
                    state.bid_size = float(size)
                elif tickType == 3:
                    state.ask_size = float(size)
                state.ts = datetime.now(tz=timezone.utc)

            def tickSnapshotEnd(self, reqId):
                """EWrapper callback: signal that the L1 snapshot is complete."""
                state = self._quotes.get(reqId)
                if state is not None:
                    state.event.set()

            def historicalTicksLast(self, reqId, ticks, done):
                """EWrapper callback: accumulate trade ticks and signal when done."""
                state = self._trades.get(reqId)
                if state is None:
                    return
                for tick in ticks:
                    conditions: Tuple[str, ...] = ()
                    if getattr(tick, "specialConditions", ""):
                        conditions = tuple(str(tick.specialConditions).split())
                    state.trades.append(
                        _RawTrade(
                            ts=datetime.fromtimestamp(int(tick.time), tz=timezone.utc),
                            price=float(tick.price),
                            size=float(tick.size),
                            venue=getattr(tick, "exchange", None),
                            conditions=conditions or None,
                            trade_id=None,
                        )
                    )
                if done:
                    state.event.set()

            def updateMktDepth(self, reqId, position, operation, side, price, size):
                """EWrapper callback: apply a depth update and set the ready event."""
                state = self._depth.get(reqId)
                if state is None:
                    return
                book = state.bids if side == 1 else state.asks
                _apply_depth_op(book, int(position), int(operation), float(price), float(size))
                state.ts = datetime.now(tz=timezone.utc)
                state.ready_event.set()

            def updateMktDepthL2(
                self,
                reqId,
                position,
                marketMaker,
                operation,
                side,
                price,
                size,
                isSmartDepth,
            ):
                """EWrapper callback: delegate SMART-depth updates to ``updateMktDepth``."""
                self.updateMktDepth(reqId, position, operation, side, price, size)

        return _IBApp()
