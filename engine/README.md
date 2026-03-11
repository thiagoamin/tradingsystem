# Engine Layer

## Goal

Implement the core trading runtime as a composable pipeline:

1. Evaluate rules on `MarketState` to emit signal events.
2. Let a strategy convert signals into desired position actions.
3. Filter actions through risk controls.
4. Execute allowed actions and update portfolio state.
5. Publish events for logging/monitoring.

## Implemeneted

- Core domain contracts:
  - `state.py`, `events.py`, `actions.py`, `strategy.py`, `risk.py`, `execution.py`.
- Signal and orchestration:
  - `engine.py` (`SignalEngine`)
  - `system.py` (`TradingSystem`)
  - `runner.py`
- Rules:
  - `PercentDropRule`
  - `MovingAverageCrossRule`
- Portfolio/accounting:
  - `portfolio.py` with fill application and mark-to-market equity.
- Event dispatch/sinks:
  - `bus.py`, `sinks.py`
- Execution engines:
  - `PaperExecution` for simulated fills.
  - `execution_ibkr.py` for live/paper IBKR order placement.
- Utility-based allocation strategy:
  - `strategies/utility_allocation.py` maps forecast signals to target positions
    via shared `allocation/` utilities.

## TODO

- `risk.py`
  - `BasicRiskManager.filter()` is currently pass-through.
  - Gross exposure and equity helper methods are TODOs.
- `strategies/basic.py`
  - `BuyDipStrategy` currently returns no actions.
  - Needs logic from signal payloads to `SetTargetPosition`.
- Additional event semantics:
  - Richer risk/order/fill metadata and consistent naming conventions.
