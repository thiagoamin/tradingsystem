# engine/execution_ibkr.py
"""IBKR execution engine — routes SetTargetPosition actions to a live/paper account."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Tuple

from .actions import Action, SetTargetPosition
from .events import Event
from .execution import ExecutionEngine, Fill
from .portfolio import Portfolio
from .state import MarketState

if TYPE_CHECKING:
    from research.fetchers.providers.ibkr import IBKRLiveFetcher


class IBKRExecution(ExecutionEngine):
    """Routes orders to an IBKR paper/live account via IBKRLiveFetcher.

    Only ``SetTargetPosition`` actions are handled; all other action types are
    silently skipped.  Each order is placed synchronously with a configurable
    timeout, and failures are emitted as ``ORDER_FAILED`` events rather than
    raising exceptions.
    """

    def __init__(self, fetcher: "IBKRLiveFetcher", order_timeout_sec: float = 30.0):
        """Initialise the execution engine.

        Args:
            fetcher: Connected ``IBKRLiveFetcher`` used to place orders.
            order_timeout_sec: Maximum seconds to wait for an order fill before
                declaring failure.
        """
        self.fetcher = fetcher
        self.order_timeout_sec = order_timeout_sec

    def execute(
        self, actions: List[Action], portfolio: Portfolio, state: MarketState
    ) -> Tuple[List[Fill], List[Event]]:
        """Execute a list of actions against the IBKR account.

        For each ``SetTargetPosition`` action the delta between the target
        quantity and the current portfolio quantity is computed.  A market order
        is placed for the delta; on success a ``Fill`` is recorded and the
        portfolio is updated; on failure an ``ORDER_FAILED`` event is appended.

        Args:
            actions: Actions produced by the strategy and risk layer.
            portfolio: Current portfolio, mutated in-place on successful fills.
            state: Current market state, used for event timestamps.

        Returns:
            A tuple of ``(fills, events)`` where ``fills`` contains one entry
            per successfully filled order and ``events`` contains any warning
            events emitted during execution.
        """
        fills: List[Fill] = []
        events: List[Event] = []

        for action in actions:
            if not isinstance(action, SetTargetPosition):
                continue

            current_qty = portfolio.get_qty(action.ticker)
            delta_qty = action.target_qty - current_qty
            if delta_qty == 0:
                continue

            try:
                avg_price, filled_qty = self.fetcher.place_order(
                    action.ticker, delta_qty, self.order_timeout_sec
                )
            except Exception as exc:
                events.append(Event(
                    ts=state.timestamp,
                    type="order",
                    name="ORDER_FAILED",
                    message=f"Order failed for {action.ticker}: {exc}",
                    severity="warn",
                ))
                continue

            if filled_qty > 0:
                signed_qty = int(filled_qty) if delta_qty > 0 else -int(filled_qty)
                portfolio.apply_fill(action.ticker, signed_qty, avg_price)
                fills.append(Fill(
                    symbol=action.ticker,
                    qty=signed_qty,
                    price=avg_price,
                    ts=datetime.now(tz=timezone.utc),
                ))

        return fills, events
